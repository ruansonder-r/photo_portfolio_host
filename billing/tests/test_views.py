"""The staff screens: who may reach them, and what they do."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from billing import services
from billing.models import BusinessSettings, Client, Document, DocumentLine, Kind, Status

from .factories import make_client, make_document, with_banking


class AccessTests(TestCase):
    """These pages carry client addresses, totals and banking details."""

    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user("ruan", password="x", is_staff=True)
        self.punter = User.objects.create_user("punter", password="x")
        self.document = services.issue(make_document(client=make_client()))
        # A draft too: the edit screen refuses issued documents by design,
        # so it needs an editable one to prove staff actually get in.
        self.draft = make_document()
        self.client_record = Client.objects.first()

    def urls(self):
        return [
            reverse("billing:document_list"),
            reverse("billing:document_create"),
            reverse("billing:document_detail", args=[self.document.pk]),
            reverse("billing:document_edit", args=[self.draft.pk]),
            # The one that is easy to forget, and the one that leaks the most.
            reverse("billing:document_pdf", args=[self.document.pk]),
            reverse("billing:client_list"),
            reverse("billing:client_create"),
            reverse("billing:client_detail", args=[self.client_record.pk]),
            reverse("billing:settings"),
        ]

    def test_anonymous_is_turned_away_everywhere(self):
        for url in self.urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("login", response["Location"])

    def test_a_signed_in_non_staff_user_is_turned_away_everywhere(self):
        self.client.force_login(self.punter)
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_staff_get_in(self):
        self.client.force_login(self.staff)
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_actions_reject_anonymous_posts(self):
        for action in ["issue", "cancel", "duplicate"]:
            url = reverse("billing:document_action", args=[self.document.pk, action])
            self.assertEqual(self.client.post(url).status_code, 302)

    def test_actions_reject_get(self):
        self.client.force_login(self.staff)
        url = reverse("billing:document_action", args=[self.document.pk, "cancel"])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_billing_pages_are_never_cached(self):
        self.client.force_login(self.staff)
        cache_control = self.client.get(reverse("billing:document_list"))["Cache-Control"]
        self.assertIn("no-store", cache_control)


class StaffTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("ruan", password="x", is_staff=True)
        self.client.force_login(self.user)


class ListTests(StaffTestCase):
    def test_it_lists_documents_and_filters_by_kind(self):
        services.issue(make_document(Kind.INVOICE, project="Conference"))
        services.issue(make_document(Kind.QUOTE, project="Wedding"))

        body = self.client.get(reverse("billing:document_list")).content.decode()
        self.assertIn("Conference", body)
        self.assertIn("Wedding", body)

        quotes = self.client.get(reverse("billing:document_list"), {"kind": "quote"})
        body = quotes.content.decode()
        self.assertIn("Wedding", body)
        self.assertNotIn("Conference", body)

    def test_it_filters_by_derived_expiry(self):
        import datetime as dt

        from django.utils import timezone

        stale = services.issue(make_document(Kind.QUOTE, project="Old quote"))
        stale.valid_until = timezone.localdate() - dt.timedelta(days=1)
        stale.save(update_fields=["valid_until"])
        services.issue(make_document(Kind.QUOTE, project="Fresh quote"))

        body = self.client.get(
            reverse("billing:document_list"), {"status": "expired"}
        ).content.decode()
        self.assertIn("Old quote", body)
        self.assertNotIn("Fresh quote", body)

    def test_the_empty_state_names_the_first_number(self):
        body = self.client.get(reverse("billing:document_list")).content.decode()
        self.assertIn("10000", body)


class FormTests(StaffTestCase):
    def payload(self, **overrides):
        data = {
            "kind": Kind.INVOICE,
            "client": "",
            "project": "Conference photography",
            "issue_date": "2026-08-26",
            "due_date": "",
            "valid_until": "",
            "adjustment_label": "",
            "adjustment_amount": "0",
            "notes": "",
            "lines-TOTAL_FORMS": "2",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-description": "Event coverage",
            "lines-0-quantity": "3",
            "lines-0-unit_price": "3000",
            "lines-0-position": "0",
            "lines-1-description": "Travel",
            "lines-1-quantity": "1",
            "lines-1-unit_price": "850",
            "lines-1-position": "1",
        }
        data.update(overrides)
        return data

    def test_creating_a_draft_with_line_items(self):
        response = self.client.post(reverse("billing:document_create"), self.payload())
        self.assertEqual(response.status_code, 302)

        document = Document.objects.get()
        self.assertTrue(document.is_draft)
        self.assertIsNone(document.number)
        self.assertEqual(document.lines.count(), 2)
        # The server recalculates rather than trusting anything posted.
        self.assertEqual(document.subtotal, Decimal("9850.00"))
        self.assertEqual(document.total, Decimal("9850.00"))

    def test_totals_are_recomputed_from_the_lines_not_the_browser(self):
        self.client.post(
            reverse("billing:document_create"),
            self.payload(**{"lines-0-unit_price": "3000", "lines-1-unit_price": "850"}),
        )
        document = Document.objects.get()
        recomputed = sum(l.line_total for l in document.lines.all())
        self.assertEqual(document.subtotal, recomputed)

    def test_an_adjustment_needs_a_label(self):
        response = self.client.post(
            reverse("billing:document_create"), self.payload(adjustment_amount="-500")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Give the adjustment a label")
        self.assertFalse(Document.objects.exists())

    def test_an_issued_document_cannot_be_opened_for_editing(self):
        invoice = services.issue(make_document())
        response = self.client.get(
            reverse("billing:document_edit", args=[invoice.pk]), follow=True
        )
        self.assertContains(response, "cannot be edited")
        self.assertEqual(response.redirect_chain[-1][0], invoice.get_absolute_url())

    def test_posting_an_edit_to_an_issued_document_changes_nothing(self):
        invoice = services.issue(make_document(lines=(("Coverage", 1, 1000),)))
        self.client.post(
            reverse("billing:document_edit", args=[invoice.pk]),
            self.payload(**{"lines-0-unit_price": "99999"}),
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("1000.00"))


class DetailAndActionTests(StaffTestCase):
    def test_the_detail_page_names_the_number_it_would_issue(self):
        draft = make_document()
        body = self.client.get(draft.get_absolute_url()).content.decode()
        self.assertIn("Issue as 10000", body)

    def test_issuing_from_the_detail_page(self):
        draft = make_document()
        self.client.post(reverse("billing:document_action", args=[draft.pk, "issue"]))
        draft.refresh_from_db()
        self.assertEqual(draft.number, 10000)
        self.assertEqual(draft.status, Status.ISSUED)

    def test_converting_a_quote_lands_on_the_new_invoice(self):
        quote = services.accept_quote(services.issue(make_document(Kind.QUOTE)))
        response = self.client.post(
            reverse("billing:document_action", args=[quote.pk, "convert"]), follow=True
        )
        invoice = Document.objects.get(kind=Kind.INVOICE)
        self.assertEqual(response.redirect_chain[-1][0], invoice.get_absolute_url())
        self.assertContains(response, "created from quote")

    def test_a_refused_action_reports_why_and_changes_nothing(self):
        quote = services.issue(make_document(Kind.QUOTE))  # sent, not accepted
        response = self.client.post(
            reverse("billing:document_action", args=[quote.pk, "convert"]), follow=True
        )
        self.assertContains(response, "Only an accepted quote")
        self.assertFalse(Document.objects.filter(kind=Kind.INVOICE).exists())

    def test_an_unknown_action_is_a_404(self):
        draft = make_document()
        response = self.client.post(
            reverse("billing:document_action", args=[draft.pk, "explode"])
        )
        self.assertEqual(response.status_code, 404)

    def test_a_draft_can_be_deleted_but_an_issued_document_cannot(self):
        draft = make_document()
        self.client.post(reverse("billing:document_delete", args=[draft.pk]))
        self.assertFalse(Document.objects.filter(pk=draft.pk).exists())

        invoice = services.issue(make_document())
        response = self.client.post(
            reverse("billing:document_delete", args=[invoice.pk]), follow=True
        )
        self.assertContains(response, "cannot be deleted")
        self.assertTrue(Document.objects.filter(pk=invoice.pk).exists())

    def test_cancel_then_reissue_through_the_screens(self):
        invoice = services.issue(make_document())
        self.client.post(reverse("billing:document_action", args=[invoice.pk, "cancel"]))
        response = self.client.post(
            reverse("billing:document_action", args=[invoice.pk, "reissue"]), follow=True
        )
        correction = Document.objects.get(replaces=invoice)
        self.assertTrue(correction.is_draft)
        self.assertEqual(response.redirect_chain[-1][0], correction.get_absolute_url())


class PdfViewTests(StaffTestCase):
    def test_it_opens_inline_in_a_new_tab(self):
        invoice = services.issue(make_document())
        response = self.client.get(reverse("billing:document_pdf", args=[invoice.pk]))

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response["Content-Disposition"].startswith("inline"))
        self.assertIn("10000", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF-"))

    def test_a_draft_pdf_renders_too(self):
        draft = make_document()
        response = self.client.get(reverse("billing:document_pdf", args=[draft.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("draft", response["Content-Disposition"])


class ClientScreenTests(StaffTestCase):
    def test_creating_a_client(self):
        self.client.post(reverse("billing:client_create"), {
            "company": "Four12", "contact_person": "Jazz",
            "email": "jazz@four12global.com", "phone": "0828139850",
            "address": "Durbanville, 7550", "notes": "",
        })
        client_record = Client.objects.get()
        self.assertEqual(client_record.company, "Four12")

    def test_the_client_page_lists_their_documents_and_albums(self):
        import datetime as dt

        from albums.models import ClientAlbum

        record = make_client()
        services.issue(make_document(client=record, project="Conference"))
        ClientAlbum.objects.create(name="Four12 Conference", date=dt.date(2026, 8, 26), client=record)

        body = self.client.get(record.get_absolute_url()).content.decode()
        self.assertIn("Conference", body)
        self.assertIn("Four12 Conference", body)

    def test_deleting_a_client_leaves_their_albums_and_documents(self):
        import datetime as dt

        from albums.models import ClientAlbum

        record = make_client()
        invoice = services.issue(make_document(client=record))
        album = ClientAlbum.objects.create(
            name="Shoot", date=dt.date(2026, 8, 26), client=record
        )
        record.delete()

        album.refresh_from_db()
        invoice.refresh_from_db()
        self.assertIsNone(album.client)
        self.assertIsNone(invoice.client)
        self.assertEqual(invoice.snapshot.client.company, "Four12")


class SettingsScreenTests(StaffTestCase):
    def test_saving_settings(self):
        response = self.client.post(reverse("billing:settings"), {
            "business_name": "Ruansonder_R Photography",
            "address": "Durbanville\nCape Town, 7550",
            "phone": "+27 82 813 9850",
            "email": "ruansonder.r@gmail.com",
            "vat_registered": "", "vat_number": "", "vat_rate": "15.00",
            "bank_name": "Standard Bank", "branch_name": "Century City",
            "branch_code": "5534", "account_holder": "MR R LABUSCHAGNE",
            "account_number": "04 121 649 0", "account_type": "CURRENT",
            "swift_code": "SBZAZAJJ",
            "default_payment_terms_days": "14",
            "default_quote_validity_days": "30",
            "default_notes": "", "accent_colour": "#8A3324",
        })
        self.assertEqual(response.status_code, 302)
        settings = BusinessSettings.load()
        self.assertEqual(settings.bank_name, "Standard Bank")
        self.assertFalse(settings.vat_registered)

    def test_switching_vat_on_without_a_number_is_refused(self):
        response = self.client.post(reverse("billing:settings"), {
            "business_name": "Ruansonder_R", "address": "", "phone": "", "email": "",
            "vat_registered": "on", "vat_number": "", "vat_rate": "15.00",
            "bank_name": "", "branch_name": "", "branch_code": "", "account_holder": "",
            "account_number": "", "account_type": "", "swift_code": "",
            "default_payment_terms_days": "14", "default_quote_validity_days": "30",
            "default_notes": "", "accent_colour": "#8A3324",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VAT number is required")
        self.assertFalse(BusinessSettings.load().vat_registered)

    def test_only_a_singleton_row_ever_exists(self):
        BusinessSettings.load()
        BusinessSettings.load()
        self.assertEqual(BusinessSettings.objects.count(), 1)
