# Generated by Django 4.2.2 on 2024-03-11 21:47

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0028_alter_occurrence_options_alter_project_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="deployment",
            name="device",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="deployments",
                to="main.device",
            ),
        ),
        migrations.AlterField(
            model_name="deployment",
            name="research_site",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="deployments",
                to="main.site",
            ),
        ),
    ]
