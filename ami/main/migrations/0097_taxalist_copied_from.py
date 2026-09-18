"""
Add ``TaxaList.copied_from``, a self-FK recording which list a copy was made
from (set by the ``copy`` action on ``TaxaListViewSet``). Schema only.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0096_taxalist_is_public"),
    ]

    operations = [
        migrations.AddField(
            model_name="taxalist",
            name="copied_from",
            field=models.ForeignKey(
                blank=True,
                help_text="The list this one was copied from, for provenance. Cleared if the source list is deleted.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="copies",
                to="main.taxalist",
            ),
        ),
    ]
