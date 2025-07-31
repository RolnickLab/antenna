from django.db import models

from ami.main.models import Project
from ami.ml.models.pipeline import Pipeline


def get_default_pipeline(project: Project) -> Pipeline | None:
    """
    Select a default pipeline to use for processing images in a project.

    This is a placeholder function that selects the pipeline with the most categories
    and which is enabled for the project.

    @TODO use project settings to determine the default pipeline
    """
    return (
        Pipeline.objects.all()
        .enabled(project=project)  # type: ignore
        .annotate(num_categories=models.Count("algorithms__category_map__labels"))
        .order_by("-num_categories", "-created_at")
        .first()
    )
