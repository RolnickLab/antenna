from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0081_s3storagesource_region"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="license",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Data license for published occurrence records. "
                    "Use an SPDX identifier (e.g. 'CC-BY-4.0', 'CC0-1.0') or a license URL. "
                    "Required by GBIF for DwC-A publication."
                ),
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="rights_holder",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Name of the organization or individual owning rights to the data.",
                max_length=255,
            ),
        ),
    ]
