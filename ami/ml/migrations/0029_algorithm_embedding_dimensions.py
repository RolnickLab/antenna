# Additive: a nullable column, and a new task type choice (no schema change for the choice).

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0028_normalize_empty_endpoint_url_to_null"),
    ]

    operations = [
        migrations.AddField(
            model_name="algorithm",
            name="embedding_dimensions",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "For a feature extractor, the length of every vector it produces. Set from the processing "
                    "service's /info or from the first vector stored; vectors of any other length are refused."
                ),
                null=True,
            ),
        ),
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
                    ("feature_extraction", "Feature Extraction"),
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
                    ("post_processing", "Post Processing"),
                    ("other", "Other"),
                    ("unknown", "Unknown"),
                ],
                default="unknown",
                max_length=255,
                null=True,
            ),
        ),
    ]
