"""Every state change a document can undergo.

Views call these; they never mutate status, numbers or snapshots themselves.
Each function that allocates a number runs in one transaction so that the
counter and the document either both move or neither does.
"""

from __future__ import annotations

import datetime as dt

from django.db import transaction
from django.utils import timezone

from .exceptions import AlreadyIssued, BillingError, NotConvertible
from .models import (
    ISSUED_STATUS,
    BusinessSettings,
    Document,
    DocumentLine,
    Kind,
    NumberSequence,
    Status,
)


def peek_next_number(kind: str) -> int | None:
    """What the next issue would allocate. Display only -- never reserves."""
    row = NumberSequence.objects.filter(kind=kind).first()
    return row.next_number if row else None


@transaction.atomic
def issue(document: Document) -> Document:
    """Allocate a number, freeze the snapshot, and move out of draft.

    The counter row is locked for the rest of the transaction, so a second
    request issuing at the same instant blocks until this one commits and then
    reads the incremented value. If anything below raises, the increment rolls
    back with it and the number is never consumed -- which is the property a
    Postgres SEQUENCE cannot give, since nextval() is non-transactional.
    """
    if not document.is_draft or document.number is not None:
        raise AlreadyIssued(
            f"{document.title} {document.display_number} has already been issued."
        )
    if not document.lines.exists():
        raise BillingError("A document needs at least one line item before it can be issued.")

    sequence = NumberSequence.objects.select_for_update().get(kind=document.kind)
    document.number = sequence.next_number
    sequence.next_number += 1
    sequence.save(update_fields=["next_number"])

    settings = BusinessSettings.load()
    document.issued_snapshot = settings.snapshot_for(document.client).to_dict()
    # Drop the cached live snapshot so the totals below are computed under the
    # VAT state we just froze, not the one read before it.
    document.__dict__.pop("snapshot", None)

    _apply_default_dates(document, settings)

    # Still a draft here, so the lock guard lets this through. commit=False so
    # the totals ride along on the single save below.
    lines = document.recalculate_totals(commit=False)

    document.status = ISSUED_STATUS[Kind(document.kind)]
    document.issued_at = timezone.now()
    document.save()
    Document.persist_line_totals(lines)
    return document


def _apply_default_dates(document: Document, settings: BusinessSettings) -> None:
    """Fill in due date or validity from settings, if left blank."""
    if document.kind == Kind.INVOICE:
        if document.due_date is None and settings.default_payment_terms_days:
            document.due_date = document.issue_date + dt.timedelta(
                days=settings.default_payment_terms_days
            )
    elif document.valid_until is None and settings.default_quote_validity_days:
        document.valid_until = document.issue_date + dt.timedelta(
            days=settings.default_quote_validity_days
        )


# --- quote transitions ---------------------------------------------------


def accept_quote(quote: Document) -> Document:
    _require_kind(quote, Kind.QUOTE)
    if quote.status != Status.SENT:
        raise BillingError("Only a sent quote can be accepted.")
    if quote.is_expired:
        raise BillingError(
            f"This quote expired on {quote.valid_until:%-d %B %Y}. "
            "Reissue it before accepting."
        )
    return _set_status(quote, Status.ACCEPTED)


def decline_quote(quote: Document) -> Document:
    _require_kind(quote, Kind.QUOTE)
    if quote.status not in {Status.SENT, Status.ACCEPTED}:
        raise BillingError("Only a sent or accepted quote can be declined.")
    return _set_status(quote, Status.DECLINED)


@transaction.atomic
def convert_quote_to_invoice(quote: Document) -> Document:
    """One click: copy the accepted quote into an invoice and issue it.

    The quote keeps its own number and status as the record; the two link to
    each other through ``converted_from``.

    Expiry is deliberately not re-checked here. ``accept_quote`` is the gate:
    a client who accepted inside the validity window struck the deal then, and
    should not be blocked because the invoice went out three months later.
    """
    _require_kind(quote, Kind.QUOTE)
    if quote.status != Status.ACCEPTED:
        raise NotConvertible("Only an accepted quote can be turned into an invoice.")

    existing = quote.invoices.first()
    if existing is not None:
        raise NotConvertible(
            f"This quote has already been invoiced as {existing.display_number}."
        )

    invoice = _copy(quote, kind=Kind.INVOICE, converted_from=quote)
    return issue(invoice)


# --- invoice transitions -------------------------------------------------


def mark_paid(invoice: Document, *, on: dt.date | None = None) -> Document:
    _require_kind(invoice, Kind.INVOICE)
    if invoice.status != Status.ISSUED:
        raise BillingError("Only an issued invoice can be marked paid.")
    invoice.paid_at = on or timezone.localdate()
    invoice.status = Status.PAID
    invoice.save(update_fields=["status", "paid_at", "updated_at"])
    return invoice


def cancel(invoice: Document) -> Document:
    """Void an issued invoice, keeping its number.

    Deliberately does not create the correction: sometimes cancelling is the
    whole intent -- a client cancels a booking -- and there is no corrected
    invoice to follow. ``reissue`` is the separate second step.
    """
    _require_kind(invoice, Kind.INVOICE)
    if invoice.is_draft:
        raise BillingError("This invoice is still a draft. Delete it instead of cancelling.")
    if invoice.status == Status.CANCELLED:
        return invoice
    if invoice.status == Status.PAID:
        raise BillingError(
            "This invoice is marked paid. Mark it unpaid first if it really needs cancelling."
        )
    return _set_status(invoice, Status.CANCELLED)


@transaction.atomic
def reissue(invoice: Document) -> Document:
    """Open a corrected draft of a cancelled invoice.

    No number is allocated here -- you edit the mistake, then issue normally,
    and it takes the next number in sequence. Cancelling never frees a number
    for reuse.
    """
    _require_kind(invoice, Kind.INVOICE)
    if invoice.status != Status.CANCELLED:
        raise BillingError("Only a cancelled invoice can be reissued as a correction.")

    existing = invoice.replaced_by.first()
    if existing is not None:
        raise BillingError(
            f"This invoice has already been corrected by "
            f"{existing.display_number or 'a draft'}."
        )

    return _copy(invoice, kind=Kind.INVOICE, replaces=invoice)


@transaction.atomic
def duplicate(document: Document) -> Document:
    """A fresh draft with the same lines. No link -- it is a new job."""
    return _copy(document, kind=Kind(document.kind))


# --- internals -----------------------------------------------------------


def _require_kind(document: Document, kind: str) -> None:
    if document.kind != kind:
        raise BillingError(f"This action applies to a {Kind(kind).label.lower()}.")


def _set_status(document: Document, status: str) -> Document:
    document.status = status
    document.save(update_fields=["status", "updated_at"])
    return document


def _copy(source: Document, *, kind: str, **links) -> Document:
    """A new draft carrying the source's content but none of its identity."""
    draft = Document.objects.create(
        kind=kind,
        status=Status.DRAFT,
        client=source.client,
        project=source.project,
        issue_date=timezone.localdate(),
        currency=source.currency,
        notes=source.notes,
        adjustment_label=source.adjustment_label,
        adjustment_amount=source.adjustment_amount,
        **links,
    )
    DocumentLine.objects.bulk_create(
        [
            DocumentLine(
                document=draft,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=line.line_total,
                position=line.position,
            )
            for line in source.lines.all()
        ]
    )
    draft.recalculate_totals()
    return draft
