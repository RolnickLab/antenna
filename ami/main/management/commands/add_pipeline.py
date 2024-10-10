import logging

from django.core.management.base import BaseCommand

from ami.main.models import Project
from ami.ml.models import Algorithm, Pipeline

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Automatically add dummy ML pipeline to Test Project."

    def handle(self, *args, **kwargs):
        # Get all projects
        projects = Project.objects.all()

        if projects:
            for project in projects:
                if "Test Project" in project.name:
                    project_name = project.name
        else:
            raise Exception("No test project found.")

        pipelines_to_add = [
            {
                "name": "ML Dummy Backend",
                "slug": "dummy",
                "version": 1,
                "algorithms": [
                    {"name": "Dummy Detector", "key": 1},
                    {"name": "Random Detector", "key": 2},
                    {"name": "Always Moth Classifier", "key": 3},
                ],
                "projects": {"name": project_name},
                # @TODO Replace with extra hosts
                "endpoint_url": "https://a5cd-24-114-29-178.ngrok-free.app/pipeline/process",
            },
        ]

        for pipeline_data in pipelines_to_add:
            # Get or create the project
            project, _ = Project.objects.get_or_create(name=pipeline_data["projects"]["name"])

            # Create or get the pipeline
            pipeline, created = Pipeline.objects.get_or_create(
                name=pipeline_data["name"],
                slug=pipeline_data["slug"],
                version=pipeline_data["version"],
                endpoint_url=pipeline_data["endpoint_url"],
            )

            if created:
                logger.info(f'Successfully created {pipeline_data["name"]}.')
            else:
                logger.warning(f'Could not create {pipeline_data["name"]}.')

            # Add related algorithms
            for algorithm_data in pipeline_data["algorithms"]:
                algorithm, _ = Algorithm.objects.get_or_create(name=algorithm_data["name"], key=algorithm_data["key"])
                pipeline.algorithms.add(algorithm)

            pipeline.save()
