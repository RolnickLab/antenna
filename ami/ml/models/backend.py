import datetime
import logging
from urllib.parse import urljoin

import requests
from django.db import models

from ami.main.models import Project
from ami.ml.schemas import BackendResponse

from .algorithm import Algorithm
from .pipeline import Pipeline

logger = logging.getLogger(__name__)


class Backend(models.Model):
    """An ML processing backend"""

    projects = models.ManyToManyField("main.Project", related_name="backends", blank=True)
    endpoint_url = models.CharField(max_length=1024, null=True, blank=True)

    def __str__(self):
        return self.endpoint_url

    class Meta:
        verbose_name = "Backend"
        verbose_name_plural = "Backends"

    def create_pipelines(self):
        # Call the status endpoint and get the pipelines/algorithms
        resp = requests.get(urljoin(self.endpoint_url, "status"))
        pipelines_to_add = resp.data.get("pipeline_configs")

        for pipeline_data in pipelines_to_add:
            pipeline, created = Pipeline.objects.get_or_create(
                name=pipeline_data["name"],
                slug=pipeline_data["slug"],
                version=pipeline_data["version"],
            )

            if created:
                logger.info(f'Successfully created pipeline {pipeline_data["name"]}.')
            else:
                logger.info(f'Using existing pipeline {pipeline_data["name"]}.')

            for algorithm_data in pipeline_data["algorithms"]:
                algorithm, created = Algorithm.objects.get_or_create(
                    name=algorithm_data["name"], key=algorithm_data["key"]
                )
                pipeline.algorithms.add(algorithm)

                if created:
                    logger.info(f'Successfully created algorithm {algorithm_data["name"]}.')
                else:
                    logger.info(f'Using existing algorithm {algorithm_data["name"]}.')

            for project_data in pipeline_data["projects"]:
                project, created = Project.objects.get_or_create(name=project_data["name"])
                pipeline.projects.add(project)

                if created:
                    logger.info(f'Successfully created project {project_data["name"]}.')
                else:
                    logger.info(f'Using existing project {project_data["name"]}.')

            # @TODO: Add pipeline description and stages

            pipeline.save()

    def get_status(self):
        info_url = urljoin(self.endpoint_url, "info")

        resp = requests.get(info_url)
        if not resp.ok:
            try:
                msg = resp.json()["detail"]
            except Exception:
                msg = resp.content

            logger.error(msg)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pipeline_configs = resp.json() if resp.ok else []
        error = f"{resp.status_code} - {msg}" if not resp.ok else None

        server_live = requests.get(urljoin(self.endpoint_url, "livez")).json().get("status")
        pipelines_online = requests.get(urljoin(self.endpoint_url, "readyz")).json().get("status")

        response = BackendResponse(
            timestamp=timestamp,
            success=resp.ok,
            server_online=server_live,
            pipelines_online=pipelines_online,
            pipeline_configs=pipeline_configs,
            endpoint_url=self.endpoint_url,
            error=error,
        )

        return response
