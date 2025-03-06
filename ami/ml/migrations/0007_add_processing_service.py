# Generated by Django 4.2.10 on 2025-01-17 19:40

import ami.base.schemas
from django.db import migrations, models
import django_pydantic_field.fields


class Migration(migrations.Migration):
    replaces = [
        ("ml", "0007_backend"),
        ("ml", "0008_remove_pipeline_endpoint_url_pipeline_backend"),
        ("ml", "0009_remove_pipeline_backend_backend_pipelines"),
        ("ml", "0010_backend_created_at_backend_updated_at"),
        ("ml", "0011_alter_pipeline_stages"),
        ("ml", "0012_backend_last_checked_backend_last_checked_live"),
        ("ml", "0013_backend_description_backend_name_backend_slug_and_more"),
        ("ml", "0014_remove_backend_version_remove_backend_version_name_and_more"),
        ("ml", "0015_processingservice_delete_backend"),
        ("ml", "0016_alter_processingservice_options"),
        ("ml", "0017_remove_processingservice_slug_and_more"),
    ]

    dependencies = [
        ("main", "0038_alter_detection_path_alter_sourceimage_event_and_more"),
        ("ml", "0006_alter_pipeline_endpoint_url_alter_pipeline_projects"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="pipeline",
            name="endpoint_url",
        ),
        migrations.AlterField(
            model_name="pipeline",
            name="stages",
            field=django_pydantic_field.fields.PydanticSchemaField(
                config=None,
                default=ami.base.schemas.default_stages,
                help_text="The stages of the pipeline. This is mainly for display. The backend implementation of the pipeline may process data in any way.",
                schema="list[PipelineStage]",
            ),
        ),
        migrations.CreateModel(
            name="ProcessingService",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("endpoint_url", models.CharField(max_length=1024)),
                ("last_checked", models.DateTimeField(null=True)),
                ("last_checked_live", models.BooleanField(null=True)),
                (
                    "pipelines",
                    models.ManyToManyField(blank=True, related_name="processing_services", to="ml.pipeline"),
                ),
                (
                    "projects",
                    models.ManyToManyField(blank=True, related_name="processing_services", to="main.project"),
                ),
                ("last_checked_latency", models.FloatField(null=True)),
            ],
            options={
                "verbose_name": "Processing Service",
                "verbose_name_plural": "Processing Services",
            },
        ),
    ]
