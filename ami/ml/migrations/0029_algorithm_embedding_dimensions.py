# Additive: a nullable column, filled in when an algorithm's first feature vector is stored.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0028_normalize_empty_endpoint_url_to_null"),
    ]

    operations = [
        migrations.AddField(
            model_name="algorithm",
            name="embedding_dimensions",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "The length of the feature vectors this algorithm has stored. Set from the first vector "
                    "stored; vectors of any other length are refused, because they could not be compared."
                ),
                null=True,
            ),
        ),
    ]
