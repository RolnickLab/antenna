# Generated by Django 4.2.10 on 2025-03-14 18:31

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0018_add_processing_services_status_check_celery_beat_task"),
    ]

    operations = [
        migrations.AlterField(
            model_name="algorithm",
            name="task_type",
            field=models.CharField(
                choices=[
                    ("detection", "Detection"),
                    ("localization", "Localization"),
                    ("segmentation", "Segmentation"),
                    ("classification", "Classification"),
                    ("embedding", "Embedding"),
                    ("tracking", "Tracking"),
                    ("tagging", "Tagging"),
                    ("regression", "Regression"),
                    ("captioning", "Captioning"),
                    ("generation", "Generation"),
                    ("translation", "Translation"),
                    ("summarization", "Summarization"),
                    ("question_answering", "Question Answering"),
                    ("depth_estimation", "Depth Estimation"),
                    ("pose_estimation", "Pose Estimation"),
                    ("size_estimation", "Size Estimation"),
                    ("other", "Other"),
                    ("unknown", "Unknown"),
                ],
                default="unknown",
                max_length=255,
                null=True,
            ),
        ),
    ]
