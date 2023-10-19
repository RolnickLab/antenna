# Generated by Django 4.2.2 on 2023-10-11 01:50

import ami.main.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("main", "0006_merge_20230926_2353"),
    ]

    operations = [
        migrations.CreateModel(
            name="SourceImageUpload",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "image",
                    models.ImageField(
                        upload_to=ami.main.models.upload_to_with_deployment,
                        validators=[ami.main.models.validate_filename_timestamp],
                    ),
                ),
                (
                    "capture",
                    models.OneToOneField(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="main.sourceimage"
                    ),
                ),
                ("deployment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="main.deployment")),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
