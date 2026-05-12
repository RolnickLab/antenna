from django.db import migrations
import pgvector.django.vector


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0084_add_pgvector_extension"),
    ]

    operations = [
        migrations.AddField(
            model_name="classification",
            name="features_2048",
            field=pgvector.django.vector.VectorField(
                dimensions=2048,
                null=True,
                help_text="Feature embedding from the model backbone",
            ),
        ),
    ]
