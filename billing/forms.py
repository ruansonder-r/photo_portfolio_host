"""Forms for the staff screens.

Every widget carries the site's own ``.field`` class so these render as part
of the site rather than as Django's default admin chrome.
"""

from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from .models import BusinessSettings, Client, Document, DocumentLine, Kind

FIELD = {"class": "field"}


def _date_input(**extra):
    return forms.DateInput(attrs={**FIELD, "type": "date", **extra}, format="%Y-%m-%d")


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            "kind", "client", "project", "issue_date", "due_date", "valid_until",
            "adjustment_label", "adjustment_amount", "notes",
        ]
        widgets = {
            "kind": forms.Select(attrs=FIELD),
            "client": forms.Select(attrs=FIELD),
            "project": forms.TextInput(attrs={**FIELD, "placeholder": "e.g. Four12 Conference"}),
            "issue_date": _date_input(),
            "due_date": _date_input(),
            "valid_until": _date_input(),
            "adjustment_label": forms.TextInput(
                attrs={**FIELD, "placeholder": "e.g. Returning client discount"}
            ),
            "adjustment_amount": forms.NumberInput(attrs={**FIELD, "step": "0.01"}),
            "notes": forms.Textarea(attrs={**FIELD, "rows": 4}),
        }
        labels = {
            "valid_until": "Valid until",
            "adjustment_label": "Adjustment label",
            "adjustment_amount": "Adjustment amount",
        }
        help_texts = {
            "due_date": "Leave blank to use your default payment terms.",
            "valid_until": "Quotes only. Leave blank to use your default validity.",
            "adjustment_amount": "Negative for a discount, positive for a surcharge.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].empty_label = "— no client —"
        # Kind decides which sequence the number comes from, so it is fixed
        # once the document exists rather than switchable underneath it.
        if self.instance.pk:
            self.fields["kind"].disabled = True

    def clean(self):
        data = super().clean()
        if data.get("adjustment_amount") and not data.get("adjustment_label"):
            self.add_error(
                "adjustment_label",
                "Give the adjustment a label -- it is printed on the document.",
            )
        return data


class DocumentLineForm(forms.ModelForm):
    class Meta:
        model = DocumentLine
        fields = ["description", "quantity", "unit_price", "position"]
        widgets = {
            "description": forms.Textarea(
                attrs={**FIELD, "rows": 1, "placeholder": "What you are charging for"}
            ),
            "quantity": forms.NumberInput(
                attrs={**FIELD, "step": "0.01", "data-line-quantity": ""}
            ),
            "unit_price": forms.NumberInput(
                attrs={**FIELD, "step": "0.01", "data-line-price": ""}
            ),
            "position": forms.HiddenInput(),
        }


DocumentLineFormSet = inlineformset_factory(
    Document,
    DocumentLine,
    form=DocumentLineForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["company", "contact_person", "email", "phone", "address", "notes"]
        widgets = {
            "company": forms.TextInput(attrs=FIELD),
            "contact_person": forms.TextInput(attrs={**FIELD, "placeholder": "Printed as “Att:”"}),
            "email": forms.EmailInput(attrs=FIELD),
            "phone": forms.TextInput(attrs={**FIELD, "placeholder": "+27 82 813 9850"}),
            "address": forms.Textarea(attrs={**FIELD, "rows": 3}),
            "notes": forms.Textarea(attrs={**FIELD, "rows": 3}),
        }


class BusinessSettingsForm(forms.ModelForm):
    class Meta:
        model = BusinessSettings
        fields = [
            "business_name", "address", "phone", "email",
            "vat_registered", "vat_number", "vat_rate",
            "bank_name", "branch_name", "branch_code", "account_holder",
            "account_number", "account_type", "swift_code",
            "default_payment_terms_days", "default_quote_validity_days",
            "default_notes", "accent_colour",
        ]
        widgets = {
            "address": forms.Textarea(attrs={**FIELD, "rows": 3}),
            "default_notes": forms.Textarea(attrs={**FIELD, "rows": 3}),
            "vat_registered": forms.CheckboxInput(),
            "vat_rate": forms.NumberInput(attrs={**FIELD, "step": "0.01"}),
            "accent_colour": forms.TextInput(attrs={**FIELD, "placeholder": "#8A3324"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name not in self.Meta.widgets:
                field.widget.attrs.setdefault("class", "field")

    def clean_vat_number(self):
        number = (self.cleaned_data.get("vat_number") or "").strip()
        if self.data.get("vat_registered") and not number:
            raise forms.ValidationError(
                "A VAT number is required once you are registered -- it is printed "
                "on every tax invoice."
            )
        return number
