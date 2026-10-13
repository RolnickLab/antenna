from django.db import migrations


def normalize_empty_endpoint_url(apps, schema_editor):
    ProcessingService = apps.get_model("ml", "ProcessingService")
    ProcessingService.objects.filter(endpoint_url="").update(endpoint_url=None)


class Migration(migrations.Migration):

    dependencies = [
        ("ml", "0027_rename_last_checked_to_last_seen"),
    ]

    operations = [
        migrations.RunPython(normalize_empty_endpoint_url, migrations.RunPython.noop),
    ]
