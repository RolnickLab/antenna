from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ml", "0026_make_processing_service_endpoint_url_nullable"),
    ]

    operations = [
        migrations.RenameField(
            model_name="processingservice",
            old_name="last_checked",
            new_name="last_seen",
        ),
        migrations.RenameField(
            model_name="processingservice",
            old_name="last_checked_live",
            new_name="last_seen_live",
        ),
        migrations.RenameField(
            model_name="processingservice",
            old_name="last_checked_latency",
            new_name="last_seen_latency",
        ),
    ]
