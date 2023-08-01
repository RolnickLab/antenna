# Generated by Django 4.2.2 on 2023-07-28 01:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0006_alter_sourceimage_options_alter_job_config_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Page",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("slug", models.CharField(max_length=255, unique=True)),
                ("content", models.TextField(blank=True, null=True)),
                ("link_class", models.CharField(blank=True, max_length=255, null=True)),
                ("nav_level", models.IntegerField(default=0)),
                ("nav_order", models.IntegerField(default=0)),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pages",
                        to="main.project",
                    ),
                ),
            ],
            options={
                "ordering": ["nav_level", "nav_order", "name"],
            },
        ),
    ]
