"""Small builders so each test states only what it is actually about."""

from decimal import Decimal

from billing.models import BusinessSettings, Client, Document, DocumentLine, Kind

# The shape of the invoice this feature replaces, as a default.
DEFAULT_LINES = (("Event Photo Shoot", 1, 3000),)


def make_client(**kwargs) -> Client:
    return Client.objects.create(
        **{
            "company": "Four12",
            "contact_person": "Jazz",
            "email": "jazz@four12global.com",
            "phone": "0828139850",
            "address": "Durbanville, 7550",
            **kwargs,
        }
    )


def make_document(kind=Kind.INVOICE, *, lines=DEFAULT_LINES, client=None, **kwargs) -> Document:
    document = Document.objects.create(
        kind=kind,
        client=client,
        project=kwargs.pop("project", "Conference photography"),
        **kwargs,
    )
    for position, (description, quantity, unit_price) in enumerate(lines):
        DocumentLine.objects.create(
            document=document,
            description=description,
            quantity=Decimal(str(quantity)),
            unit_price=Decimal(str(unit_price)),
            position=position,
        )
    document.recalculate_totals()
    return document


def vat_on(rate="15.00") -> BusinessSettings:
    settings = BusinessSettings.load()
    settings.vat_registered = True
    settings.vat_number = "4123456789"
    settings.vat_rate = Decimal(rate)
    settings.save()
    return settings


def with_banking(**overrides) -> BusinessSettings:
    settings = BusinessSettings.load()
    for field, value in {
        "bank_name": "Standard Bank",
        "branch_name": "Century City",
        "branch_code": "5534",
        "account_holder": "MR R LABUSCHAGNE",
        "account_number": "04 121 649 0",
        "account_type": "CURRENT",
        "swift_code": "SBZAZAJJ",
        **overrides,
    }.items():
        setattr(settings, field, value)
    settings.save()
    return settings
