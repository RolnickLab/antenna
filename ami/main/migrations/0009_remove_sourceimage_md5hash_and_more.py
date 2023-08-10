# Generated by Django 4.2.2 on 2023-08-09 22:55

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0008_page_published"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="sourceimage",
            name="md5hash",
        ),
        migrations.AddField(
            model_name="deployment",
            name="data_source_last_checked",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sourceimage",
            name="checksum",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="sourceimage",
            name="checksum_algorithm",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="sourceimage",
            name="last_modified",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sourceimage",
            name="source",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="page",
            name="content",
            field=models.TextField(
                blank=True, help_text="Use Markdown syntax", null=True, verbose_name="Body content"
            ),
        ),
        migrations.AlterField(
            model_name="page",
            name="link_class",
            field=models.CharField(blank=True, help_text="CSS class for nav link", max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="page",
            name="nav_level",
            field=models.IntegerField(default=0, help_text="0 = main nav, 1 = sub nav, etc."),
        ),
        migrations.AlterField(
            model_name="page",
            name="nav_order",
            field=models.IntegerField(default=0, help_text="Order of nav items within a level"),
        ),
        migrations.AlterField(
            model_name="page",
            name="slug",
            field=models.CharField(help_text="Unique, URL safe name e.g. about-us", max_length=255, unique=True),
        ),
    ]
