import typing

from ami.jobs.models import Job
from ami.ml.models import Pipeline
from ami.ml.orchestration.pipelines import get_default_pipeline

if typing.TYPE_CHECKING:
    from ami.main.models import SourceImage


def process_single_source_image(
    source_image: "SourceImage",
    pipeline: "Pipeline | None" = None,
    run_async=True,
) -> "Job":
    """
    Process a single SourceImage immediately.
    """

    assert source_image.deployment is not None, "SourceImage must belong to a deployment"

    if not source_image.event:
        source_image.deployment.save(regroup_async=False)
        source_image.refresh_from_db()
    assert source_image.event is not None, "SourceImage must belong to an event"

    project = source_image.project
    assert project is not None, "SourceImage must belong to a project"

    pipeline_choice = pipeline or get_default_pipeline(project)
    assert pipeline_choice is not None, "Project must have a pipeline to run"

    # @TODO add images to a queue without creating a job for each image
    job = Job.objects.create(
        name=f"Capture #{source_image.pk} ({source_image.timestamp}) from {source_image.deployment.name}",
        job_type_key="ml",
        source_image_single=source_image,
        pipeline=pipeline_choice,
        project=project,
    )
    if run_async:
        job.enqueue()
    else:
        job.run()
    return job
