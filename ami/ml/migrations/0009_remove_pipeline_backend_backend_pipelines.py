# Generated by Django 4.2.10 on 2024-11-14 19:36

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0008_remove_pipeline_endpoint_url_pipeline_backend"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="pipeline",
            name="backend",
        ),
        migrations.AddField(
            model_name="backend",
            name="pipelines",
            field=models.ManyToManyField(blank=True, related_name="backends", to="ml.pipeline"),
        ),
    ]