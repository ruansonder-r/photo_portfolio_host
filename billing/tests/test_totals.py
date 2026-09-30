"""Money arithmetic: Decimal throughout, half-up, rounded per line then summed."""

from decimal import Decimal

from django.test import TestCase

from billing import services
from billing.models import Document, DocumentLine
from billing.money import format_money, format_quantity, quantize

from .factories import make_document, vat_on


class RoundingTests(TestCase):
    def test_half_up_not_bankers(self):
        """0.5 x 4.69 is exactly 2.345. Banker's rounding gives 2.34, which
        disagrees with every bank statement this gets reconciled against."""
        self.assertEqual(quantize(Decimal("2.345")), Decimal("2.35"))
        self.assertEqual(quantize(Decimal("2.335")), Decimal("2.34"))
        self.assertEqual(quantize(Decimal("0.005")), Decimal("0.01"))

    def test_line_total_is_quantity_times_price(self):
        document = make_document(lines=(("Coverage", "0.50", "4.69"),))
        line = document.lines.get()
        self.assertEqual(line.line_total, Decimal("2.35"))

    def test_lines_are_rounded_individually_then_summed(self):
        """Three lines of 2.345. Rounded per line: 2.35 x 3 = 7.05.
        Summed first and rounded once: 7.035 -> 7.04. The client adding up the
        printed column gets 7.05, so that is what the subtotal must say."""
        document = make_document(lines=(("A", "0.50", "4.69"),) * 3)
        self.assertEqual(document.subtotal, Decimal("7.05"))
        self.assertEqual(
            [line.line_total for line in document.lines.all()], [Decimal("2.35")] * 3
        )

    def test_thousands_and_decimals(self):
        self.assertEqual(format_money(9850), "9 850.00")
        self.assertEqual(format_money(Decimal("1234567.891")), "1 234 567.89")
        self.assertEqual(format_money(850, currency="ZAR"), "R 850.00")
        self.assertEqual(format_money(-500), "-500.00")

    def test_quantity_drops_meaningless_decimals(self):
        self.assertEqual(format_quantity(Decimal("1.00")), "1")
        self.assertEqual(format_quantity(Decimal("1.50")), "1.5")
        self.assertEqual(format_quantity(Decimal("2.25")), "2.25")


class TotalsTests(TestCase):
    def test_subtotal_is_the_sum_of_lines(self):
        document = make_document(
            lines=(("Event coverage", 3, 3000), ("Travel", 1, 850)),
        )
        self.assertEqual(document.subtotal, Decimal("9850.00"))
        self.assertEqual(document.total, Decimal("9850.00"))

    def test_a_discount_reduces_and_a_surcharge_increases(self):
        document = make_document(
            lines=(("Coverage", 1, 1000),), adjustment_amount=Decimal("-250.00")
        )
        document.recalculate_totals()
        self.assertEqual(document.total, Decimal("750.00"))

        document.adjustment_amount = Decimal("125.00")
        document.recalculate_totals()
        self.assertEqual(document.total, Decimal("1125.00"))

    def test_with_vat_off_the_total_is_the_subtotal_plus_adjustment(self):
        document = make_document(
            lines=(("Coverage", 1, 1000),), adjustment_amount=Decimal("-100.00")
        )
        document.recalculate_totals()
        self.assertEqual(document.vat_amount, Decimal("0.00"))
        self.assertEqual(document.total, Decimal("900.00"))
        self.assertFalse(document.shows_vat)

    def test_vat_applies_to_the_post_adjustment_net(self):
        """Exclusive: the discount comes off first, then VAT is added on top."""
        vat_on("15.00")
        document = make_document(
            lines=(("Event coverage", 3, 3000), ("Travel", 1, 850)),
            adjustment_amount=Decimal("-500.00"),
        )
        document.recalculate_totals()

        self.assertEqual(document.subtotal, Decimal("9850.00"))
        self.assertEqual(document.net, Decimal("9350.00"))
        self.assertEqual(document.vat_amount, Decimal("1402.50"))
        self.assertEqual(document.total, Decimal("10752.50"))

    def test_vat_is_added_not_extracted(self):
        """The inclusive/exclusive decision, pinned. Exclusive means the client
        pays more than the quoted line, not that you absorb the VAT."""
        vat_on("15.00")
        document = make_document(lines=(("Coverage", 1, 3000),))
        document.recalculate_totals()
        self.assertEqual(document.total, Decimal("3450.00"))

    def test_zero_quantity_and_zero_price_lines(self):
        document = make_document(
            lines=(("Free consult", 1, 0), ("Cancelled item", 0, 5000)),
        )
        self.assertEqual(document.subtotal, Decimal("0.00"))
        self.assertEqual(document.total, Decimal("0.00"))

    def test_stored_totals_match_a_fresh_recomputation(self):
        document = make_document(
            lines=(("A", "1.5", "333.33"), ("B", 2, "99.99"), ("C", "0.5", "4.69")),
            adjustment_amount=Decimal("-13.37"),
        )
        document.recalculate_totals()
        stored = (document.subtotal, document.vat_amount, document.total)

        fresh = Document.objects.get(pk=document.pk)
        fresh.recalculate_totals(commit=False)
        self.assertEqual((fresh.subtotal, fresh.vat_amount, fresh.total), stored)

    def test_floats_never_reach_the_stored_value(self):
        """0.1 + 0.1 + 0.1 must be 0.30, not 0.30000000000000004."""
        document = make_document(lines=(("Tenth", 1, 0.10),) * 3)
        self.assertEqual(document.subtotal, Decimal("0.30"))
        for line in document.lines.all():
            self.assertIsInstance(line.line_total, Decimal)
            self.assertEqual(line.line_total, Decimal("0.10"))

    def test_totals_are_frozen_once_issued(self):
        document = services.issue(make_document(lines=(("Coverage", 1, 1000),)))
        with self.assertRaises(Exception):
            document.recalculate_totals()

    def test_line_items_cannot_be_changed_once_issued(self):
        document = services.issue(make_document(lines=(("Coverage", 1, 1000),)))
        line = document.lines.get()
        line.unit_price = Decimal("99999.00")
        with self.assertRaises(Exception):
            line.save()
        with self.assertRaises(Exception):
            line.delete()
        with self.assertRaises(Exception):
            DocumentLine.objects.create(
                document=document, description="Sneaky extra", quantity=1, unit_price=5000
            )

        document.refresh_from_db()
        self.assertEqual(document.total, Decimal("1000.00"))
