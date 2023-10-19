# Generated by Django 4.2.2 on 2023-10-16 23:42

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("main", "0007_sourceimageupload"),
    ]

    operations = [
        migrations.RenameField(
            model_name="sourceimageupload",
            old_name="capture",
            new_name="source_image",
        ),
        migrations.AddField(
            model_name="sourceimage",
            name="test_image",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="sourceimage",
            name="uploaded_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
