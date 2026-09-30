"""Seed the two number sequences and the settings singleton.

Invoices start at 10000 and quotes at 1000, each on its own counter. The
settings row is created here rather than lazily so that the first person to
open the settings screen edits a row that already exists.
"""

from django.db import migrations

INVOICE_START = 10000
QUOTE_START = 1000


def seed(apps, schema_editor):
    NumberSequence = apps.get_model("billing", "NumberSequence")
    BusinessSettings = apps.get_model("billing", "BusinessSettings")

    NumberSequence.objects.bulk_create(
        [
            NumberSequence(kind="invoice", next_number=INVOICE_START),
            NumberSequence(kind="quote", next_number=QUOTE_START),
        ],
        ignore_conflicts=True,
    )

    if not BusinessSettings.objects.filter(pk=1).exists():
        # Imported rather than hard-coded so the defaults stay in one place.
        from billing.models import BusinessSettings as Live

        BusinessSettings.objects.create(pk=1, **Live.env_defaults())


def unseed(apps, schema_editor):
    apps.get_model("billing", "NumberSequence").objects.all().delete()
    apps.get_model("billing", "BusinessSettings").objects.filter(pk=1).delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
