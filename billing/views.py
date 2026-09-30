"""Staff screens for quotes and invoices.

Every view here is staff-only and never cached: these pages carry client
addresses, totals and your banking details.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from core.auth import is_admin_user

from . import services
from .exceptions import BillingError
from .forms import BusinessSettingsForm, ClientForm, DocumentForm, DocumentLineFormSet
from .models import BusinessSettings, Client, Document, Kind, Status
from .pdf import render_document


def staff_page(view):
    """Logged in, staff, and never stored by a browser, proxy or CDN."""
    return login_required(user_passes_test(is_admin_user)(never_cache(view)))


# --- documents -----------------------------------------------------------


@staff_page
def document_list(request):
    documents = Document.objects.select_related("client")

    kind = request.GET.get("kind") or ""
    status = request.GET.get("status") or ""

    if kind in Kind.values:
        documents = documents.filter(kind=kind)

    today = timezone.localdate()
    if status == "expired":
        # Derived, so it is a query rather than a stored value.
        documents = documents.filter(
            kind=Kind.QUOTE, status=Status.SENT, valid_until__lt=today
        )
    elif status == "overdue":
        documents = documents.filter(
            kind=Kind.INVOICE, status=Status.ISSUED, due_date__lt=today
        )
    elif status in Status.values:
        documents = documents.filter(status=status)

    return render(request, "billing/document_list.html", {
        "documents": documents,
        "kind": kind,
        "status": status,
        "kinds": Kind.choices,
        "statuses": list(Status.choices) + [("expired", "Expired"), ("overdue", "Overdue")],
        "page_title": "Quotes & invoices",
    })


@staff_page
def document_detail(request, pk):
    document = get_object_or_404(
        Document.objects.select_related("client", "converted_from", "replaces"), pk=pk
    )
    # Shown on the Issue button so the number is never a surprise. A peek,
    # not a reservation -- it is allocated under a lock at issue time.
    next_number_display = ""
    if document.is_draft:
        upcoming = services.peek_next_number(document.kind)
        if upcoming is not None:
            next_number_display = (
                f"Q{upcoming}" if document.kind == Kind.QUOTE else str(upcoming)
            )

    return render(request, "billing/document_detail.html", {
        "document": document,
        "next_number_display": next_number_display,
        "lines": document.lines.all(),
        "snapshot": document.snapshot,
        "invoice_from_quote": document.invoices.first(),
        "correction": document.replaced_by.first(),
        "page_title": f"{document.title} {document.display_number or 'draft'}",
    })


@staff_page
def document_form(request, pk=None):
    document = get_object_or_404(Document, pk=pk) if pk else None

    if document and document.is_locked:
        messages.error(
            request,
            f"{document.title} {document.display_number} has been issued and cannot "
            "be edited. Cancel it and reissue a correction instead.",
        )
        return redirect(document.get_absolute_url())

    if request.method == "POST":
        form = DocumentForm(request.POST, instance=document)
        formset = DocumentLineFormSet(request.POST, instance=document)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                document = form.save()
                formset.instance = document
                formset.save()
                _renumber_lines(document)
                # Authoritative: whatever the browser computed is a convenience.
                document.recalculate_totals()
            messages.success(request, "Saved.")
            return redirect(document.get_absolute_url())
    else:
        initial = {}
        if document is None:
            settings = BusinessSettings.load()
            initial = {"kind": request.GET.get("kind") or Kind.INVOICE,
                       "notes": settings.default_notes}
        form = DocumentForm(instance=document, initial=initial)
        formset = DocumentLineFormSet(instance=document)

    return render(request, "billing/document_form.html", {
        "form": form,
        "formset": formset,
        "document": document,
        "next_numbers": {
            Kind.INVOICE: services.peek_next_number(Kind.INVOICE),
            Kind.QUOTE: services.peek_next_number(Kind.QUOTE),
        },
        "page_title": "Edit document" if document else "New document",
    })


def _renumber_lines(document) -> None:
    """Keep `position` dense and in the order the rows were submitted."""
    lines = list(document.lines.all())
    for index, line in enumerate(lines):
        line.position = index
    if lines:
        type(lines[0]).objects.bulk_update(lines, ["position"])


@staff_page
def document_pdf(request, pk):
    """Opens in a new tab: inline, not an attachment.

    The filename still applies if it is saved out of the viewer.
    """
    document = get_object_or_404(Document.objects.select_related("client"), pk=pk)
    name = f"{document.title} {document.display_number or 'draft'}".replace(" ", "-")
    response = HttpResponse(render_document(document), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{name}.pdf"'
    return response


ACTIONS = {
    "issue": services.issue,
    "accept": services.accept_quote,
    "decline": services.decline_quote,
    "convert": services.convert_quote_to_invoice,
    "mark-paid": services.mark_paid,
    "cancel": services.cancel,
    "reissue": services.reissue,
    "duplicate": services.duplicate,
}


@require_POST
@staff_page
def document_action(request, pk, action):
    document = get_object_or_404(Document, pk=pk)
    handler = ACTIONS.get(action)
    if handler is None:
        raise Http404("Unknown action")

    try:
        result = handler(document)
    except BillingError as exc:
        messages.error(request, str(exc))
        return redirect(document.get_absolute_url())

    messages.success(request, _confirmation(action, document, result))
    # Actions that produce a new document land you on the new one.
    return redirect(result.get_absolute_url())


def _confirmation(action, document, result) -> str:
    if action == "convert":
        return f"Invoice {result.display_number} created from quote {document.display_number}."
    if action == "reissue":
        return (
            f"Correction opened as a draft. It takes the next number when you issue it "
            f"-- {document.display_number} stays cancelled."
        )
    if action == "duplicate":
        return "Duplicated as a new draft."
    if action == "issue":
        return f"Issued as {result.display_number}."
    if action == "cancel":
        return f"{document.title} {document.display_number} cancelled. It keeps its number."
    return "Done."


@require_POST
@staff_page
def document_delete(request, pk):
    document = get_object_or_404(Document, pk=pk)
    try:
        document.delete()
    except BillingError as exc:
        messages.error(request, str(exc))
        return redirect(document.get_absolute_url())
    messages.success(request, "Draft deleted.")
    return redirect("billing:document_list")


# --- clients -------------------------------------------------------------


@staff_page
def client_list(request):
    return render(request, "billing/client_list.html", {
        "clients": Client.objects.all(),
        "page_title": "Clients",
    })


@staff_page
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    return render(request, "billing/client_detail.html", {
        "client": client,
        "documents": client.documents.all(),
        # The optional link to client albums, if one has been made.
        "albums": client.albums.all(),
        "page_title": client.company,
    })


@staff_page
def client_form(request, pk=None):
    client = get_object_or_404(Client, pk=pk) if pk else None
    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save()
            messages.success(request, "Client saved.")
            return redirect(client.get_absolute_url())
    else:
        form = ClientForm(instance=client)

    return render(request, "billing/client_form.html", {
        "form": form,
        "client": client,
        "page_title": "Edit client" if client else "New client",
    })


# --- settings ------------------------------------------------------------


@staff_page
def settings_form(request):
    settings = BusinessSettings.load()
    if request.method == "POST":
        form = BusinessSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Settings saved. Documents already issued keep the details they "
                "were issued with.",
            )
            return redirect("billing:settings")
    else:
        form = BusinessSettingsForm(instance=settings)

    return render(request, "billing/settings_form.html", {
        "form": form,
        "page_title": "Business settings",
    })
