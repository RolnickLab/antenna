# Additive: an empty table. The vector column is stored uncompressed out of line (STORAGE
# EXTERNAL): vectors do not compress, and it keeps the table's rows small. See #1453.

import django.db.models.deletion
import django.utils.timezone
import pgvector.django.halfvec
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0029_algorithm_embedding_dimensions"),
        ("jobs", "0023_alter_job_job_type_key"),
        ("main", "0096_enable_pgvector_extension"),
    ]

    operations = [
        migrations.CreateModel(
            name="DetectionEmbedding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(default="embedding", max_length=255)),
                (
                    "vector",
                    pgvector.django.halfvec.HalfVectorField(help_text="The feature vector, in half precision."),
                ),
                ("timestamp", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "algorithm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="detection_embeddings",
                        to="ml.algorithm",
                    ),
                ),
                (
                    "detection",
                    models.ForeignKey(
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="embeddings",
                        to="main.detection",
                    ),
                ),
                (
                    "job",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="detection_embeddings",
                        to="jobs.job",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="detection_embeddings",
                        to="main.project",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="detectionembedding",
            constraint=models.CheckConstraint(
                check=models.Q(("key", ""), _negated=True), name="main_detectionembedding_key_not_empty"
            ),
        ),
        migrations.AddConstraint(
            model_name="detectionembedding",
            constraint=models.UniqueConstraint(
                fields=("detection", "algorithm", "key"), name="main_detectionembedding_unique_detection_algorithm_key"
            ),
        ),
        migrations.RunSQL(
            sql="ALTER TABLE main_detectionembedding ALTER COLUMN vector SET STORAGE EXTERNAL",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
