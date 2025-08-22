from django.db import models


class ProjectSettingsMixin(models.Model):
    """
    User definable settings for projects.

    This is a mixin that will be flattened out into the final model.
    It allows us to organize user-defined project settings in their own class
    without needing to create a separate model.
    """

    default_processing_pipeline = models.ForeignKey(
        "ml.Pipeline",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_projects",
        help_text=(
            "The default pipeline to use for processing images in this project. "
            "This is used to determine which processing service to run on new images. "
            # "Use the global unique key of the Pipeline, which may be a slug or a UUID. "
            # "Cannot be a Pipeline instance yet, because the Pipelines have likely not been created yet."
        ),
    )

    session_time_gap_seconds = models.IntegerField(
        default=60 * 60 * 2,  # Default to 2 hours
        help_text="Time gap in seconds to consider a new session",
    )

    default_filters_score_threshold = models.FloatField(
        default=0.5,
        help_text="Default score threshold for filtering occurrences",
    )

    default_filters_include_taxa = models.ManyToManyField(
        "Taxon",
        related_name="include_taxa_default_projects",
        blank=True,
        help_text=(
            "Taxa that are included by default in the occurrence filters and metrics. "
            "For example, the top-level taxa like 'Moths' or 'Arthropods'. "
        ),
    )

    default_filters_exclude_taxa = models.ManyToManyField(
        "Taxon",
        related_name="exclude_taxa_default_projects",
        blank=True,
        help_text=(
            "Taxa that are excluded by default in the occurrence filters and metrics. " "For example, 'Not a Moth'."
        ),
    )

    # settings_updated_at = models.DateTimeField(auto_now=True, help_text="Last time any setting was updated")

    class Meta:
        # Do not create a separate table for this mixin
        abstract = True

    @classmethod
    def get_settings_field_names(cls) -> list[str]:
        """
        Automatically discover settings fields by comparing with BaseModel.

        This finds fields that exist in the final model but not in BaseModel,
        which means they were added by this mixin.
        """
        from ami.base.models import BaseModel  # Adjust import as needed

        # Get all field names from the final model
        all_fields = {f.name for f in cls._meta.get_fields()}

        # Get all field names from BaseModel
        base_fields = {f.name for f in BaseModel._meta.get_fields()}

        # Settings fields are those not in BaseModel
        settings_fields = all_fields - base_fields

        # Filter out reverse relations and other auto-generated fields
        real_settings_fields = []
        for field_name in settings_fields:
            try:
                field = cls._meta.get_field(field_name)
                # Skip auto-created fields and foreign key ID fields
                if not (field.auto_created or field.name.endswith("_id")):
                    real_settings_fields.append(field_name)
            except Exception:
                # Skip fields that can't be retrieved (like reverse relations)
                continue

        return sorted(real_settings_fields)
