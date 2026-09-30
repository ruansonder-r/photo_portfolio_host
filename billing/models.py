"""Quotes and invoices.

One ``Document`` model carries both kinds. They have the same shape -- client,
project, line items, totals, notes, banking block -- so two models would mean
two renderers, two list screens, and a conversion that copies between tables.
The cost is a nullable ``number`` and per-kind status validation, both of which
the database enforces.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from functools import cached_property

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from .exceptions import DocumentLocked
from .money import ZERO, format_money, format_quantity, quantize, to_decimal
from .snapshots import BankSnapshot, BusinessSnapshot, ClientSnapshot, DocumentSnapshot

# Invoices start here. Quotes run their own sequence from QUOTE_START.
INVOICE_START = 10000
QUOTE_START = 1000


class Kind(models.TextChoices):
    QUOTE = "quote", "Quote"
    INVOICE = "invoice", "Invoice"


class Status(models.TextChoices):
    DRAFT = "draft", "Draft"
    # Quote
    SENT = "sent", "Sent"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    # Invoice
    ISSUED = "issued", "Issued"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"


# `expired` is deliberately absent: a quote is expired when valid_until has
# passed, derived the way ClientAlbum.is_available already works. No cron job,
# no rows drifting out of date.
STATUSES_BY_KIND = {
    Kind.QUOTE: [Status.DRAFT, Status.SENT, Status.ACCEPTED, Status.DECLINED],
    Kind.INVOICE: [Status.DRAFT, Status.ISSUED, Status.PAID, Status.CANCELLED],
}

# The status a document moves into when its number is allocated.
ISSUED_STATUS = {Kind.QUOTE: Status.SENT, Kind.INVOICE: Status.ISSUED}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


class BusinessSettings(models.Model):
    """Your details, editable from the browser rather than by redeploying.

    Deliberately separate from ``core.context_processors.site_info``, which
    reads the same facts from environment variables for the public site.
    Unifying them would put a database query on every public gallery render,
    on a connection that opens fresh each request, to save typing a phone
    number twice. Seeded from those env vars on first create.
    """

    singleton_id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    business_name = models.CharField(max_length=200)
    address = models.TextField(blank=True, help_text="One line per line. Printed as written.")
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)

    vat_registered = models.BooleanField(
        default=False,
        help_text="Off: documents are titled “Invoice” with no VAT line. "
                  "On: “Tax Invoice”, with your VAT number and a VAT breakdown.",
    )
    vat_number = models.CharField(max_length=30, blank=True)
    vat_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("15.00"),
        help_text="Percent. Only used when VAT is switched on.",
    )

    bank_name = models.CharField(max_length=100, blank=True)
    branch_name = models.CharField(max_length=100, blank=True)
    branch_code = models.CharField(max_length=20, blank=True)
    account_holder = models.CharField(max_length=150, blank=True)
    account_number = models.CharField(max_length=40, blank=True)
    account_type = models.CharField(max_length=40, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)

    default_payment_terms_days = models.PositiveSmallIntegerField(
        default=14, help_text="Due date offered on a new invoice, in days from the issue date."
    )
    default_quote_validity_days = models.PositiveSmallIntegerField(
        default=30, help_text="How long a new quote stays open, in days."
    )
    default_notes = models.TextField(
        blank=True, help_text="Pre-filled into the notes field on a new document."
    )
    accent_colour = models.CharField(
        max_length=7, default="#8A3324",
        help_text="The single accent used on the PDF. Hex, e.g. #8A3324.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "business settings"
        verbose_name_plural = "business settings"

    def __str__(self) -> str:
        return self.business_name or "Business settings"

    def save(self, *args, **kwargs):
        self.singleton_id = 1
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise DocumentLocked("Business settings cannot be deleted, only edited.")

    @classmethod
    def load(cls) -> "BusinessSettings":
        obj, _ = cls.objects.get_or_create(pk=1, defaults=cls.env_defaults())
        return obj

    @classmethod
    def env_defaults(cls) -> dict:
        """First-run values, borrowed from the public site's configuration."""
        return {
            "business_name": _env("PHOTOGRAPHER_NAME", "Ruansonder_R"),
            "address": _env("PHOTOGRAPHER_LOCATION", "Cape Town, South Africa"),
            "phone": _env("PHOTOGRAPHER_WHATSAPP", "+27 82 813 9850"),
            "email": _env("PHOTOGRAPHER_EMAIL", "ruansonder.r@gmail.com"),
        }

    def snapshot_for(self, client: "Client | None") -> DocumentSnapshot:
        """Everything a document must keep saying, as it stands right now."""
        return DocumentSnapshot(
            business=BusinessSnapshot(
                name=self.business_name,
                address=self.address,
                phone=self.phone,
                email=self.email,
            ),
            bank=BankSnapshot(
                bank_name=self.bank_name,
                branch_name=self.branch_name,
                branch_code=self.branch_code,
                account_holder=self.account_holder,
                account_number=self.account_number,
                account_type=self.account_type,
                swift_code=self.swift_code,
            ),
            client=ClientSnapshot(
                company=client.company if client else "",
                contact_person=client.contact_person if client else "",
                email=client.email if client else "",
                phone=client.phone if client else "",
                address=client.address if client else "",
            ),
            vat_registered=self.vat_registered,
            vat_number=self.vat_number,
            vat_rate=self.vat_rate,
            accent_colour=self.accent_colour,
        )


class Client(models.Model):
    """A customer. Reusable across documents and, optionally, client albums."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.CharField(max_length=200, help_text="The customer or company name")
    contact_person = models.CharField(
        max_length=200, blank=True, help_text="Printed as “Att:” on the document"
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True, help_text="Internal. Never printed.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company"]

    def __str__(self) -> str:
        return self.company

    def get_absolute_url(self) -> str:
        return reverse("billing:client_detail", kwargs={"pk": self.pk})


class NumberSequence(models.Model):
    """One counter row per kind, incremented under a row lock.

    A Postgres SEQUENCE would be the obvious choice and is the wrong one:
    nextval() is non-transactional, so a rolled-back issue burns the number
    and leaves a gap. This row rolls back with the transaction that touched it.
    """

    kind = models.CharField(max_length=20, choices=Kind.choices, primary_key=True)
    next_number = models.PositiveIntegerField()

    class Meta:
        verbose_name = "number sequence"
        verbose_name_plural = "number sequences"

    def __str__(self) -> str:
        return f"{self.get_kind_display()}: next {self.next_number}"


class Document(models.Model):
    """A quote or an invoice."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.INVOICE)
    # Null until issued. That is the whole answer to "no gaps from abandoned
    # drafts": an abandoned draft never held a number to leave behind.
    number = models.PositiveIntegerField(null=True, blank=True, editable=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)

    client = models.ForeignKey(
        Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="documents"
    )
    project = models.CharField(max_length=200, blank=True)

    # The date printed on the document. Editable -- you may issue today for
    # last week's shoot. Distinct from issued_at, which is when the number was
    # actually allocated and is never editable.
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    valid_until = models.DateField(
        null=True, blank=True, help_text="Quotes only. After this date the quote is expired."
    )

    currency = models.CharField(max_length=3, default="ZAR")
    notes = models.TextField(blank=True)

    adjustment_label = models.CharField(
        max_length=120, blank=True, help_text="e.g. “Returning client discount”"
    )
    adjustment_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO,
        help_text="Negative for a discount, positive for a surcharge.",
    )

    # Real columns, not properties: the list screen sorts and sums on them in
    # one query, and they are the audit record if a rounding rule ever changes.
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, editable=False)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, editable=False)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, editable=False)

    issued_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    issued_at = models.DateTimeField(null=True, blank=True, editable=False)
    paid_at = models.DateField(null=True, blank=True)

    converted_from = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="invoices", editable=False,
        help_text="On an invoice: the quote it was generated from.",
    )
    replaces = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="replaced_by", editable=False,
        help_text="On a reissued invoice: the cancelled one it corrects.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issue_date", "-created_at"]
        indexes = [
            models.Index(fields=["kind", "status"]),
            models.Index(fields=["kind", "-number"]),
            models.Index(fields=["client"]),
        ]
        constraints = [
            # Backstop under the row lock in services.allocate_number: even a
            # bug cannot produce two invoice 10001s. Partial, so any number of
            # drafts can coexist with number IS NULL.
            models.UniqueConstraint(
                fields=["kind", "number"],
                condition=models.Q(number__isnull=False),
                name="billing_unique_number_per_kind",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(kind=Kind.QUOTE, status__in=STATUSES_BY_KIND[Kind.QUOTE])
                    | models.Q(kind=Kind.INVOICE, status__in=STATUSES_BY_KIND[Kind.INVOICE])
                ),
                name="billing_status_matches_kind",
            ),
            # A draft has no number; anything else has one.
            models.CheckConstraint(
                condition=(
                    models.Q(status=Status.DRAFT, number__isnull=True)
                    | (~models.Q(status=Status.DRAFT) & models.Q(number__isnull=False))
                ),
                name="billing_number_iff_issued",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} {self.display_number or '(draft)'}"

    def get_absolute_url(self) -> str:
        return reverse("billing:document_detail", kwargs={"pk": self.pk})

    # --- state ----------------------------------------------------------

    @property
    def is_draft(self) -> bool:
        return self.status == Status.DRAFT

    @property
    def is_locked(self) -> bool:
        """Issued documents are immutable. Cancel-and-reissue is the exit."""
        return not self.is_draft

    @property
    def is_expired(self) -> bool:
        """Derived, never stored -- see the note on STATUSES_BY_KIND."""
        return (
            self.kind == Kind.QUOTE
            and self.status == Status.SENT
            and self.valid_until is not None
            and self.valid_until < timezone.localdate()
        )

    @property
    def is_overdue(self) -> bool:
        return (
            self.kind == Kind.INVOICE
            and self.status == Status.ISSUED
            and self.due_date is not None
            and self.due_date < timezone.localdate()
        )

    @property
    def state_label(self) -> str:
        """What the status pill says, including the two derived states."""
        if self.is_expired:
            return "Expired"
        if self.is_overdue:
            return "Overdue"
        return self.get_status_display()

    # --- identity -------------------------------------------------------

    @property
    def display_number(self) -> str:
        if self.number is None:
            return ""
        return f"Q{self.number}" if self.kind == Kind.QUOTE else str(self.number)

    @property
    def title(self) -> str:
        """Renders under the VAT setting that applied when it was issued."""
        if self.kind == Kind.QUOTE:
            return "Quotation"
        return "Tax Invoice" if self.snapshot.vat_registered else "Invoice"

    @property
    def number_label(self) -> str:
        return "Quote #" if self.kind == Kind.QUOTE else "Invoice #"

    @property
    def client_label(self) -> str:
        return "Quote for" if self.kind == Kind.QUOTE else "Invoice for"

    @cached_property
    def snapshot(self) -> DocumentSnapshot:
        """Frozen details for an issued document; live ones for a draft."""
        if self.issued_snapshot:
            return DocumentSnapshot.from_dict(self.issued_snapshot)
        return BusinessSettings.load().snapshot_for(self.client)

    # --- money ----------------------------------------------------------

    def recalculate_totals(self, *, commit: bool = True) -> list["DocumentLine"]:
        """Recompute line totals and the four stored columns.

        Each line total is rounded to cents individually and the rounded values
        summed -- not summed at full precision and rounded once. That matches
        what a client sees when they add up the column themselves, which is
        the only reconciliation that ever actually happens.

        Returns the lines with their totals set, so a caller mid-issue can
        persist them alongside its own single write.
        """
        if self.is_locked:
            raise DocumentLocked(
                f"{self.title} {self.display_number} has been issued; its totals are frozen."
            )
        lines = list(self.lines.all())
        for line in lines:
            line.line_total = quantize(to_decimal(line.quantity) * to_decimal(line.unit_price))

        self.subtotal = sum((line.line_total for line in lines), ZERO)
        net = self.subtotal + to_decimal(self.adjustment_amount)

        snapshot = self.snapshot
        if snapshot.vat_registered:
            # Exclusive: VAT is added on top of the post-adjustment net.
            self.vat_amount = quantize(net * snapshot.vat_rate / Decimal("100"))
        else:
            self.vat_amount = ZERO

        self.total = net + self.vat_amount

        if commit:
            self.persist_line_totals(lines)
            Document.objects.filter(pk=self.pk).update(
                subtotal=self.subtotal, vat_amount=self.vat_amount, total=self.total
            )
        return lines

    @staticmethod
    def persist_line_totals(lines: list["DocumentLine"]) -> None:
        """Write computed line totals in one query.

        bulk_update deliberately bypasses DocumentLine.save() and its lock
        check: issue() has to write these totals on the document it is in the
        middle of locking. Every other write path goes through save().
        """
        if lines:
            DocumentLine.objects.bulk_update(lines, ["line_total"])

    @property
    def net(self) -> Decimal:
        """Subtotal after the adjustment, before VAT."""
        return to_decimal(self.subtotal) + to_decimal(self.adjustment_amount)

    @property
    def has_adjustment(self) -> bool:
        return to_decimal(self.adjustment_amount) != ZERO

    @property
    def shows_vat(self) -> bool:
        return bool(self.snapshot.vat_registered)

    def money(self, value) -> str:
        return format_money(value, currency=self.currency)

    @property
    def total_display(self) -> str:
        return self.money(self.total)

    # --- guards ---------------------------------------------------------

    def clean(self):
        allowed = STATUSES_BY_KIND.get(Kind(self.kind), [])
        if self.status not in allowed:
            raise ValidationError(
                {"status": f"A {self.get_kind_display().lower()} cannot be “{self.status}”."}
            )

    def delete(self, *args, **kwargs):
        """An issued document is never deleted -- that is the other half of
        "no gaps". A wrong invoice is cancelled, keeping its number."""
        if self.is_locked:
            raise DocumentLocked(
                f"{self.title} {self.display_number} has been issued and cannot be deleted. "
                "Cancel it instead."
            )
        return super().delete(*args, **kwargs)


class DocumentLine(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="lines")
    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO, editable=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return self.description[:60]

    def _assert_editable(self):
        if self.document_id and self.document.is_locked:
            raise DocumentLocked(
                "This document has been issued. Its line items cannot be changed."
            )

    def save(self, *args, **kwargs):
        self._assert_editable()
        self.line_total = quantize(to_decimal(self.quantity) * to_decimal(self.unit_price))
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._assert_editable()
        return super().delete(*args, **kwargs)

    @property
    def quantity_display(self) -> str:
        return format_quantity(self.quantity)

    @property
    def unit_price_display(self) -> str:
        return format_money(self.unit_price)

    @property
    def line_total_display(self) -> str:
        return format_money(self.line_total)
