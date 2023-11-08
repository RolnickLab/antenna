# Generated by Django 4.2.2 on 2023-11-02 00:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("main", "0015_delete_job"),
    ]

    operations = [
        migrations.CreateModel(
            name="Job",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                (
                    "config",
                    models.JSONField(
                        default={
                            "stages": [
                                {
                                    "key": "delay_test",
                                    "name": "Delay test",
                                    "params": [{"key": "delay_seconds", "name": "Delay seconds", "value": 10}],
                                }
                            ]
                        },
                        null=True,
                    ),
                ),
                ("queue", models.CharField(default="default", max_length=255)),
                ("scheduled_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("CREATED", "CREATED"),
                            ("PENDING", "PENDING"),
                            ("STARTED", "STARTED"),
                            ("SUCCESS", "SUCCESS"),
                            ("FAILURE", "FAILURE"),
                            ("RETRY", "RETRY"),
                            ("REVOKED", "REVOKED"),
                            ("RECEIVED", "RECEIVED"),
                        ],
                        default="CREATED",
                        max_length=255,
                    ),
                ),
                (
                    "progress",
                    models.JSONField(
                        default={
                            "stages": [
                                {
                                    "input_size": 0,
                                    "key": "delay_test",
                                    "output_size": 0,
                                    "progress": 0,
                                    "status": "PENDING",
                                    "status_label": "0% completed.",
                                    "time_elapsed": 0,
                                    "time_remaining": None,
                                }
                            ],
                            "summary": {"progress": 0, "status": "CREATED", "status_label": "0% completed."},
                        },
                        null=True,
                    ),
                ),
                ("result", models.JSONField(blank=True, null=True)),
                ("task_id", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "deployment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="jobs",
                        to="main.deployment",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="jobs", to="main.project"
                    ),
                ),
                (
                    "source_image_collection",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="jobs",
                        to="main.sourceimagecollection",
                    ),
                ),
                (
                    "source_image_single",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="jobs",
                        to="main.sourceimage",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]