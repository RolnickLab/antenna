"""
Rewords TaxaList.is_public's help text from "available" to "shown": is_public
only affects visibility, not whether other subsystems still filter by project
link. Schema-only, no data change.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0096_taxalist_is_public"),
    ]

    operations = [
        migrations.AlterField(
            model_name="taxalist",
            name="is_public",
            field=models.BooleanField(
                default=False,
                help_text="Public rows are shown to every project, not just the ones linked via 'projects'.",
            ),
        ),
    ]
