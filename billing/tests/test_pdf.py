"""The PDF renderer.

Text is read back out with pypdf (a test-only dependency) so these assert what
a client would actually see, rather than that some bytes were produced.
"""

import datetime as dt
import io
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from billing import services
from billing.models import BusinessSettings, Document, DocumentLine, Kind
from billing.pdf import render_document

from .factories import make_client, make_document, vat_on, with_banking


def text_of(pdf: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf))
    return "\n".join(page.extract_text() for page in reader.pages)


def page_count(pdf: bytes) -> int:
    from pypdf import PdfReader

    return len(PdfReader(io.BytesIO(pdf)).pages)


class RenderTests(TestCase):
    def setUp(self):
        with_banking()
        settings = BusinessSettings.load()
        settings.business_name = "Ruansonder_R Photography"
        settings.phone = "828139850"  # exactly how the old invoice stored it
        settings.save()

    def test_it_produces_a_pdf(self):
        pdf = render_document(services.issue(make_document(client=make_client())))
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertEqual(page_count(pdf), 1)

    def test_the_number_total_and_phone_appear(self):
        invoice = services.issue(
            make_document(client=make_client(), lines=(("Event coverage", 3, 3000),))
        )
        text = text_of(render_document(invoice))

        self.assertIn("10000", text)
        self.assertIn("9 000.00", text)          # thousands separated -- fault 8
        self.assertIn("+27 82 813 9850", text)   # not 828139850 -- fault 6
        self.assertIn("Four12", text)
        self.assertIn("Att: Jazz", text)
        self.assertIn("Standard Bank", text)

    def test_only_real_rows_are_rendered(self):
        """Fault 1: the old invoice padded to four rows and printed 0.00 three
        times."""
        invoice = services.issue(make_document(lines=(("Event Photo Shoot", 1, 3000),)))
        text = text_of(render_document(invoice))

        self.assertEqual(text.count("Event Photo Shoot"), 1)
        # Exactly four figures: unit price, line total, subtotal, total. The
        # old invoice would have shown three more rows of 0.00 besides.
        self.assertEqual(text.count("3 000.00"), 4)

    def test_empty_fields_are_omitted_entirely(self):
        """Fault 2: no "Notes:" label with nothing after it, and no Due date
        line when there is no due date."""
        settings = BusinessSettings.load()
        settings.default_payment_terms_days = 0  # so no due date is derived
        settings.save()

        invoice = services.issue(make_document(notes="", adjustment_amount=Decimal("0")))
        text = text_of(render_document(invoice))

        self.assertNotIn("NOTES", text.upper())
        self.assertNotIn("DUE", text.upper())
        self.assertNotIn("ADJUSTMENT", text.upper())
        self.assertNotIn("VAT", text.upper())

    def test_present_fields_are_rendered(self):
        invoice = services.issue(
            make_document(
                notes="Payment by EFT please.",
                adjustment_label="Returning client discount",
                adjustment_amount=Decimal("-500.00"),
            )
        )
        text = text_of(render_document(invoice))

        self.assertIn("Payment by EFT please.", text)
        self.assertIn("Returning client discount", text)
        self.assertIn("-500.00", text)
        # Column labels are set uppercase by the Label flowable.
        self.assertIn("DUE", text.upper())

    def test_dates_are_unambiguous(self):
        """26 August 2026, not 26/08/2026 -- which means two different days
        depending on who is reading it."""
        invoice = services.issue(make_document(issue_date=dt.date(2026, 8, 26)))
        text = text_of(render_document(invoice))
        self.assertIn("26 August 2026", text)
        self.assertNotIn("26/08/2026", text)

    def test_vat_off_is_titled_invoice_with_no_vat_line(self):
        text = text_of(render_document(services.issue(make_document())))
        self.assertIn("Invoice", text)
        self.assertNotIn("Tax Invoice", text)
        self.assertNotIn("VAT", text)

    def test_vat_on_is_titled_tax_invoice_and_shows_the_breakdown(self):
        vat_on("15.00")
        invoice = services.issue(
            make_document(client=make_client(), lines=(("Event coverage", 3, 3000),))
        )
        text = text_of(render_document(invoice))

        self.assertIn("Tax Invoice", text)
        self.assertIn("VAT @ 15%", text)
        self.assertIn("1 350.00", text)
        self.assertIn("4123456789", text)

    def test_a_long_invoice_spills_with_a_repeating_header(self):
        invoice = services.issue(
            make_document(lines=tuple((f"Album spread {n}", 1, 450) for n in range(40)))
        )
        pdf = render_document(invoice)
        self.assertGreater(page_count(pdf), 1)

        from pypdf import PdfReader

        pages = [p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages]
        for index, page in enumerate(pages):
            self.assertIn("UNIT PRICE", page.upper(), f"page {index + 1} lost the table header")

    def test_the_total_never_lands_on_a_page_alone(self):
        """Widow control: the closing line items travel with the totals."""
        invoice = services.issue(
            make_document(lines=tuple((f"Album spread {n}", 1, 450) for n in range(40)))
        )
        from pypdf import PdfReader

        pages = [p.extract_text() for p in PdfReader(io.BytesIO(render_document(invoice))).pages]
        last = pages[-1]
        self.assertIn("Total", last)
        self.assertIn("Album spread", last)

    def test_a_long_description_wraps_rather_than_overflowing(self):
        long_text = (
            "Full-day event coverage including two photographers, on-site backup, "
            "same-day selects delivery and a bespoke online gallery hosted for "
            "twelve months from the date of delivery"
        )
        invoice = services.issue(make_document(lines=((long_text, 1, 12500),)))
        text = text_of(render_document(invoice))
        self.assertIn("Full-day event coverage", text)
        self.assertIn("twelve months", text)

    def test_a_draft_renders_with_no_number(self):
        draft = make_document()
        text = text_of(render_document(draft))
        self.assertIn("Draft", text)
        self.assertNotIn("10000", text)

    def test_a_cancelled_invoice_keeps_its_number_and_says_so(self):
        invoice = services.issue(make_document())
        services.cancel(invoice)
        text = text_of(render_document(Document.objects.get(pk=invoice.pk)))
        self.assertIn("10000", text)
        self.assertIn("CANCELLED", text.upper())

    def test_a_quote_renders_as_a_quotation(self):
        quote = services.issue(make_document(Kind.QUOTE))
        text = text_of(render_document(quote))
        self.assertIn("Quotation", text)
        self.assertIn("Q1000", text)
        self.assertIn("VALID UNTIL", text.upper())

    def test_it_survives_a_document_with_nothing_filled_in(self):
        """No client, no project, no notes, no banking details."""
        BusinessSettings.objects.filter(pk=1).update(
            bank_name="", branch_name="", branch_code="", account_holder="",
            account_number="", account_type="", swift_code="", address="", phone="",
        )
        bare = Document.objects.create(kind=Kind.INVOICE)
        DocumentLine.objects.create(
            document=bare, description="Coverage", quantity=1, unit_price=Decimal("100")
        )
        bare.recalculate_totals()

        pdf = render_document(Document.objects.get(pk=bare.pk))
        self.assertTrue(pdf.startswith(b"%PDF-"))

    def test_a_malformed_accent_colour_does_not_break_rendering(self):
        settings = BusinessSettings.load()
        settings.accent_colour = "not-a-colour"
        settings.save()
        pdf = render_document(services.issue(make_document()))
        self.assertTrue(pdf.startswith(b"%PDF-"))
