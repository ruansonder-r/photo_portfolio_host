"""An issued document keeps saying what it said when it was issued."""

from decimal import Decimal

from django.test import TestCase

from billing import services
from billing.models import BusinessSettings, Document, Kind

from .factories import make_client, make_document, vat_on, with_banking


def reload(document: Document) -> Document:
    """Fresh instance: Document.snapshot is a cached_property."""
    return Document.objects.get(pk=document.pk)


class SnapshotTests(TestCase):
    def test_changing_bank_details_does_not_rewrite_an_issued_invoice(self):
        """The sharpest case. An invoice is a payment instruction: reprinting
        10000 with a new account, after the client paid the old one, breaks
        reconciliation and looks like fraud."""
        with_banking()
        invoice = services.issue(make_document(client=make_client()))

        with_banking(account_number="99 999 999 9", bank_name="Nedbank")

        self.assertEqual(reload(invoice).snapshot.bank.account_number, "04 121 649 0")
        self.assertEqual(reload(invoice).snapshot.bank.bank_name, "Standard Bank")
        # A new document does pick up the change.
        self.assertEqual(make_document().snapshot.bank.account_number, "99 999 999 9")

    def test_renaming_a_client_does_not_rewrite_an_issued_invoice(self):
        client = make_client()
        invoice = services.issue(make_document(client=client))

        client.company = "Four12 Global"
        client.contact_person = "Someone Else"
        client.save()

        snapshot = reload(invoice).snapshot
        self.assertEqual(snapshot.client.company, "Four12")
        self.assertEqual(snapshot.client.contact_person, "Jazz")

    def test_registering_for_vat_does_not_retitle_old_invoices(self):
        """Your explicit requirement, and a tax misstatement if it failed."""
        before = services.issue(make_document())
        self.assertEqual(before.title, "Invoice")

        vat_on()

        after = services.issue(make_document())
        self.assertEqual(reload(before).title, "Invoice")
        self.assertFalse(reload(before).shows_vat)
        self.assertEqual(reload(before).vat_amount, Decimal("0.00"))
        self.assertEqual(after.title, "Tax Invoice")
        self.assertTrue(after.shows_vat)

    def test_changing_the_vat_rate_does_not_restate_an_issued_invoice(self):
        vat_on("15.00")
        invoice = services.issue(make_document(lines=(("Coverage", 1, 1000),)))
        self.assertEqual(invoice.vat_amount, Decimal("150.00"))

        vat_on("18.00")

        reloaded = reload(invoice)
        self.assertEqual(reloaded.snapshot.vat_rate, Decimal("15.00"))
        self.assertEqual(reloaded.vat_amount, Decimal("150.00"))
        self.assertEqual(reloaded.total, Decimal("1150.00"))

    def test_a_draft_reflects_current_settings_and_stores_no_snapshot(self):
        settings = BusinessSettings.load()
        settings.business_name = "Ruansonder_R Photography"
        settings.save()

        draft = make_document()
        self.assertEqual(draft.issued_snapshot, {})
        self.assertEqual(draft.snapshot.business.name, "Ruansonder_R Photography")

        settings.business_name = "Something Else"
        settings.save()
        self.assertEqual(reload(draft).snapshot.business.name, "Something Else")

    def test_deleting_a_client_leaves_the_document_intact(self):
        """SET_NULL is safe precisely because the snapshot already has a copy."""
        client = make_client()
        invoice = services.issue(make_document(client=client))
        client.delete()

        reloaded = reload(invoice)
        self.assertIsNone(reloaded.client)
        self.assertEqual(reloaded.snapshot.client.company, "Four12")
        self.assertEqual(reloaded.snapshot.client.contact_person, "Jazz")

    def test_the_phone_number_is_snapshotted_and_formatted(self):
        settings = BusinessSettings.load()
        settings.phone = "828139850"  # exactly how the old invoice stored it
        settings.save()

        invoice = services.issue(make_document(client=make_client()))
        self.assertEqual(reload(invoice).snapshot.business.phone_display, "+27 82 813 9850")
        self.assertEqual(reload(invoice).snapshot.client.phone_display, "+27 82 813 9850")

    def test_quotes_are_titled_quotation_regardless_of_vat(self):
        self.assertEqual(make_document(Kind.QUOTE).title, "Quotation")
        vat_on()
        self.assertEqual(make_document(Kind.QUOTE).title, "Quotation")
