# Generated by Django 4.2.10 on 2025-04-27 13:28

import ami.ml.schemas
from django.db import migrations
import django_pydantic_field.fields


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0021_pipeline_default_config"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pipeline",
            name="default_config",
            field=django_pydantic_field.fields.PydanticSchemaField(
                blank=True,
                config=None,
                default=dict,
                help_text="The default configuration for the pipeline. Used by both the job sending images to the pipeline and the processing service.",
                schema=ami.ml.schemas.PipelineRequestConfigParameters,
            ),
        ),
    ]
