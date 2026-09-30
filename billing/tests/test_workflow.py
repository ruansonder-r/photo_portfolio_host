"""Quote acceptance, conversion, cancellation and reissue."""

import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from billing import services
from billing.exceptions import BillingError, NotConvertible
from billing.models import Document, Kind, NumberSequence, Status

from .factories import make_client, make_document

LINES = (("Event coverage", 3, 3000), ("Travel", 1, 850))


def accepted_quote(**kwargs) -> Document:
    quote = services.issue(make_document(Kind.QUOTE, lines=LINES, **kwargs))
    return services.accept_quote(quote)


class ConversionTests(TestCase):
    def test_converting_copies_every_line(self):
        quote = accepted_quote(client=make_client())
        invoice = services.convert_quote_to_invoice(quote)

        self.assertEqual(invoice.kind, Kind.INVOICE)
        self.assertEqual(
            [(l.description, l.quantity, l.unit_price) for l in invoice.lines.all()],
            [(l.description, l.quantity, l.unit_price) for l in quote.lines.all()],
        )
        self.assertEqual(invoice.total, quote.total)
        self.assertEqual(invoice.client, quote.client)
        self.assertEqual(invoice.project, quote.project)

    def test_the_quote_survives_and_the_two_link(self):
        quote = accepted_quote()
        invoice = services.convert_quote_to_invoice(quote)

        quote.refresh_from_db()
        self.assertEqual(quote.status, Status.ACCEPTED)
        self.assertEqual(quote.number, 1000)
        self.assertEqual(invoice.converted_from, quote)
        self.assertEqual(list(quote.invoices.all()), [invoice])

    def test_the_invoice_takes_a_number_from_the_invoice_sequence(self):
        invoice = services.convert_quote_to_invoice(accepted_quote())
        self.assertEqual(invoice.number, 10000)
        self.assertEqual(invoice.display_number, "10000")
        self.assertEqual(NumberSequence.objects.get(kind=Kind.QUOTE).next_number, 1001)

    def test_converting_issues_immediately(self):
        invoice = services.convert_quote_to_invoice(accepted_quote())
        self.assertEqual(invoice.status, Status.ISSUED)
        self.assertIsNotNone(invoice.issued_at)
        self.assertTrue(invoice.issued_snapshot)

    def test_an_unaccepted_quote_cannot_be_converted(self):
        sent = services.issue(make_document(Kind.QUOTE))
        with self.assertRaises(NotConvertible):
            services.convert_quote_to_invoice(sent)

        draft = make_document(Kind.QUOTE)
        with self.assertRaises(NotConvertible):
            services.convert_quote_to_invoice(draft)

        self.assertEqual(NumberSequence.objects.get(kind=Kind.INVOICE).next_number, 10000)

    def test_a_second_conversion_is_refused_and_burns_no_number(self):
        quote = accepted_quote()
        services.convert_quote_to_invoice(quote)

        with self.assertRaises(NotConvertible):
            services.convert_quote_to_invoice(quote)

        self.assertEqual(NumberSequence.objects.get(kind=Kind.INVOICE).next_number, 10001)
        self.assertEqual(Document.objects.filter(kind=Kind.INVOICE).count(), 1)

    def test_an_expired_quote_cannot_be_accepted(self):
        """Acceptance is the gate, so this is where expiry has to bite."""
        quote = services.issue(make_document(Kind.QUOTE))
        quote.valid_until = timezone.localdate() - dt.timedelta(days=1)
        quote.save(update_fields=["valid_until"])

        with self.assertRaises(BillingError):
            services.accept_quote(quote)
        quote.refresh_from_db()
        self.assertEqual(quote.status, Status.SENT)

    def test_an_accepted_quote_stays_convertible_after_its_validity_window(self):
        """Deliberate. The client struck the deal inside the window; invoicing
        it three months later is the photographer's business, not a reason to
        refuse. Expiry is checked at acceptance, never again."""
        quote = accepted_quote()
        quote.valid_until = timezone.localdate() - dt.timedelta(days=90)
        quote.save(update_fields=["valid_until"])

        invoice = services.convert_quote_to_invoice(quote)
        self.assertEqual(invoice.number, 10000)


class ExpiryTests(TestCase):
    def test_expiry_is_derived_not_stored(self):
        quote = services.issue(make_document(Kind.QUOTE))
        self.assertFalse(quote.is_expired)

        quote.valid_until = timezone.localdate() - dt.timedelta(days=1)
        quote.save(update_fields=["valid_until"])

        fresh = Document.objects.get(pk=quote.pk)
        self.assertTrue(fresh.is_expired)
        # Nothing was written to reach that conclusion.
        self.assertEqual(fresh.status, Status.SENT)
        self.assertEqual(fresh.state_label, "Expired")

    def test_issuing_a_quote_applies_the_default_validity(self):
        quote = services.issue(make_document(Kind.QUOTE))
        self.assertEqual(quote.valid_until, quote.issue_date + dt.timedelta(days=30))

    def test_issuing_an_invoice_applies_the_default_payment_terms(self):
        invoice = services.issue(make_document())
        self.assertEqual(invoice.due_date, invoice.issue_date + dt.timedelta(days=14))

    def test_an_explicit_due_date_is_left_alone(self):
        chosen = timezone.localdate() + dt.timedelta(days=60)
        invoice = services.issue(make_document(due_date=chosen))
        self.assertEqual(invoice.due_date, chosen)


class CancelAndReissueTests(TestCase):
    def test_cancelling_keeps_the_number_and_the_totals(self):
        invoice = services.issue(make_document(lines=LINES))
        services.cancel(invoice)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Status.CANCELLED)
        self.assertEqual(invoice.number, 10000)
        self.assertEqual(invoice.total, Decimal("9850.00"))

    def test_reissue_opens_a_draft_with_no_number(self):
        invoice = services.issue(make_document(lines=LINES))
        services.cancel(invoice)
        correction = services.reissue(invoice)

        self.assertTrue(correction.is_draft)
        self.assertIsNone(correction.number)
        self.assertEqual(correction.replaces, invoice)
        self.assertEqual(
            [l.description for l in correction.lines.all()],
            [l.description for l in invoice.lines.all()],
        )
        self.assertEqual(correction.total, invoice.total)

    def test_cancelling_never_frees_a_number_for_reuse(self):
        invoice = services.issue(make_document())
        services.cancel(invoice)
        correction = services.issue(services.reissue(invoice))

        self.assertEqual(invoice.number, 10000)
        self.assertEqual(correction.number, 10001)

    def test_the_two_documents_link_in_both_directions(self):
        invoice = services.issue(make_document())
        services.cancel(invoice)
        correction = services.reissue(invoice)

        self.assertEqual(correction.replaces, invoice)
        self.assertEqual(list(invoice.replaced_by.all()), [correction])

    def test_a_draft_is_deleted_not_cancelled(self):
        with self.assertRaises(BillingError):
            services.cancel(make_document())

    def test_a_paid_invoice_is_not_cancelled_silently(self):
        invoice = services.mark_paid(services.issue(make_document()))
        with self.assertRaises(BillingError):
            services.cancel(invoice)

    def test_only_a_cancelled_invoice_can_be_reissued(self):
        invoice = services.issue(make_document())
        with self.assertRaises(BillingError):
            services.reissue(invoice)

    def test_an_invoice_is_corrected_only_once(self):
        invoice = services.issue(make_document())
        services.cancel(invoice)
        services.reissue(invoice)
        with self.assertRaises(BillingError):
            services.reissue(invoice)

    def test_marking_paid_records_the_date(self):
        invoice = services.mark_paid(services.issue(make_document()))
        self.assertEqual(invoice.status, Status.PAID)
        self.assertEqual(invoice.paid_at, timezone.localdate())

    def test_overdue_is_derived(self):
        invoice = services.issue(make_document())
        invoice.due_date = timezone.localdate() - dt.timedelta(days=1)
        invoice.save(update_fields=["due_date"])

        fresh = Document.objects.get(pk=invoice.pk)
        self.assertTrue(fresh.is_overdue)
        self.assertEqual(fresh.state_label, "Overdue")
        self.assertEqual(fresh.status, Status.ISSUED)

    def test_duplicate_makes_an_unlinked_draft(self):
        invoice = services.issue(make_document(lines=LINES))
        copy = services.duplicate(invoice)

        self.assertTrue(copy.is_draft)
        self.assertIsNone(copy.number)
        self.assertIsNone(copy.replaces)
        self.assertIsNone(copy.converted_from)
        self.assertEqual(copy.total, invoice.total)
