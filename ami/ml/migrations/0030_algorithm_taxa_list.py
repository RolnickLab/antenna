"""
``Algorithm.taxa_list`` links an algorithm to the TaxaList that mirrors its category
map (see ``Algorithm.sync_taxa_list()``). Schema only: nothing is linked or synced here.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0096_taxalist_is_public"),
        ("ml", "0029_processingservice_is_public"),
    ]

    operations = [
        migrations.AddField(
            model_name="algorithm",
            name="taxa_list",
            field=models.ForeignKey(
                blank=True,
                help_text="The taxa list that mirrors this algorithm's category map. See sync_taxa_list().",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="algorithms",
                to="main.taxalist",
            ),
        ),
    ]
