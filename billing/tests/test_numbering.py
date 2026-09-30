"""Numbers are allocated on issue, never reused, and never leave gaps."""

import threading
from unittest import mock

from django.db import connection
from django.db.models import QuerySet
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature

from billing import services
from billing.exceptions import AlreadyIssued, DocumentLocked
from billing.models import Document, Kind, NumberSequence, Status

from .factories import make_document


class SequenceTests(TestCase):
    def test_first_invoice_is_10000(self):
        invoice = services.issue(make_document())
        self.assertEqual(invoice.number, 10000)
        self.assertEqual(invoice.display_number, "10000")

    def test_numbers_increment(self):
        first = services.issue(make_document())
        second = services.issue(make_document())
        self.assertEqual([first.number, second.number], [10000, 10001])

    def test_quotes_run_their_own_sequence(self):
        quote = services.issue(make_document(Kind.QUOTE))
        invoice = services.issue(make_document(Kind.INVOICE))
        another_quote = services.issue(make_document(Kind.QUOTE))

        self.assertEqual(quote.number, 1000)
        self.assertEqual(invoice.number, 10000)
        # An invoice issued in between must not advance the quote counter.
        self.assertEqual(another_quote.number, 1001)
        self.assertEqual(another_quote.display_number, "Q1001")

    def test_a_draft_has_no_number(self):
        draft = make_document()
        self.assertIsNone(draft.number)
        self.assertEqual(draft.display_number, "")
        self.assertTrue(draft.is_draft)

    def test_abandoned_drafts_leave_no_gap(self):
        """The requirement, stated directly: drafts never hold a number."""
        for _ in range(5):
            make_document().delete()

        self.assertEqual(services.issue(make_document()).number, 10000)

    def test_a_failed_issue_consumes_no_number(self):
        """The test that proves the design.

        A Postgres SEQUENCE would have burnt 10000 here, because nextval() is
        not transactional. The counter row rolls back with the transaction.
        """
        document = make_document()
        boom = RuntimeError("Neon went away mid-issue")

        with mock.patch(
            "billing.services.BusinessSettings.load", side_effect=boom
        ), self.assertRaises(RuntimeError):
            services.issue(document)

        self.assertEqual(NumberSequence.objects.get(kind=Kind.INVOICE).next_number, 10000)
        document.refresh_from_db()
        self.assertIsNone(document.number)
        self.assertEqual(document.status, Status.DRAFT)

        # And the number is still available to the next document that asks.
        self.assertEqual(services.issue(make_document()).number, 10000)

    def test_issuing_twice_raises(self):
        invoice = services.issue(make_document())
        with self.assertRaises(AlreadyIssued):
            services.issue(invoice)
        self.assertEqual(NumberSequence.objects.get(kind=Kind.INVOICE).next_number, 10001)

    def test_a_document_with_no_lines_cannot_be_issued(self):
        empty = Document.objects.create(kind=Kind.INVOICE, project="Nothing yet")
        with self.assertRaises(Exception):
            services.issue(empty)
        self.assertEqual(NumberSequence.objects.get(kind=Kind.INVOICE).next_number, 10000)

    def test_an_issued_document_cannot_be_deleted(self):
        """The other half of "no gaps": a wrong invoice is cancelled, not erased."""
        invoice = services.issue(make_document())
        with self.assertRaises(DocumentLocked):
            invoice.delete()
        self.assertTrue(Document.objects.filter(pk=invoice.pk).exists())

    def test_a_draft_can_be_deleted(self):
        draft = make_document()
        draft.delete()
        self.assertFalse(Document.objects.filter(pk=draft.pk).exists())

    def test_issue_takes_a_row_lock_on_the_counter(self):
        """Portable guard on the lock itself.

        On SQLite, select_for_update() is silently dropped from the SQL -- the
        backend reports has_select_for_update = False -- so asserting on the
        generated SQL only works on Postgres (below). Spying on the call
        catches the regression that actually matters: someone removing the
        lock. It runs on every backend.
        """
        locked_models = []
        original = QuerySet.select_for_update

        def spy(self, *args, **kwargs):
            locked_models.append(self.model)
            return original(self, *args, **kwargs)

        with mock.patch.object(QuerySet, "select_for_update", spy):
            services.issue(make_document())

        self.assertIn(NumberSequence, locked_models)

    @skipUnlessDBFeature("has_select_for_update")
    def test_the_lock_reaches_the_database(self):
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as queries:
            services.issue(make_document())

        self.assertTrue(
            any("FOR UPDATE" in q["sql"].upper() for q in queries),
            "the counter row was read without a lock",
        )


class ConcurrentIssueTests(TransactionTestCase):
    """Real threads, real connections. Meaningless on SQLite, where the global
    write lock would serialise the writes regardless of whether we asked for a
    row lock -- so it would pass for the wrong reason."""

    available_apps = ["core", "portfolio", "albums", "billing"]

    @skipUnlessDBFeature("has_select_for_update")
    def test_two_simultaneous_issues_get_different_numbers(self):
        NumberSequence.objects.update_or_create(
            kind=Kind.INVOICE, defaults={"next_number": 10000}
        )
        documents = [make_document() for _ in range(2)]
        barrier = threading.Barrier(len(documents))
        numbers, errors = [], []

        def worker(document):
            try:
                barrier.wait(timeout=5)
                numbers.append(services.issue(document).number)
            except Exception as exc:  # surfaced below rather than swallowed
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(d,)) for d in documents]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertEqual(sorted(numbers), [10000, 10001])
