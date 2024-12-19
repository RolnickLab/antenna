import datetime
import logging
import time
import typing
from urllib.parse import urljoin

import requests
from django.db import models

from ami.base.models import BaseModel
from ami.main.models import Project
from ami.ml.models.algorithm import Algorithm
from ami.ml.models.pipeline import Pipeline
from ami.ml.schemas import BackendStatusResponse, PipelineRegistrationResponse

logger = logging.getLogger(__name__)


@typing.final
class Backend(BaseModel):
    """An ML processing backend"""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    projects = models.ManyToManyField("main.Project", related_name="backends", blank=True)
    endpoint_url = models.CharField(max_length=1024)
    pipelines = models.ManyToManyField("ml.Pipeline", related_name="backends", blank=True)
    last_checked = models.DateTimeField(null=True)
    last_checked_live = models.BooleanField(null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Backend"
        verbose_name_plural = "Backends"

    def create_pipelines(self):
        # Call the status endpoint and get the pipelines/algorithms
        resp = self.get_status()
        pipelines_to_add = resp.pipeline_configs
        pipelines = []
        pipelines_created = []
        algorithms_created = []
        projects_created = []

        for pipeline_data in pipelines_to_add:
            pipeline, created = Pipeline.objects.get_or_create(
                name=pipeline_data.name,
                slug=pipeline_data.slug,
                version=pipeline_data.version,
                description=pipeline_data.description or "",
            )
            self.pipelines.add(pipeline)

            if created:
                logger.info(f"Successfully created pipeline {pipeline.name}.")
                pipelines_created.append(pipeline.slug)
            else:
                logger.info(f"Using existing pipeline {pipeline.name}.")

            for algorithm_data in pipeline_data.algorithms:
                algorithm, created = Algorithm.objects.get_or_create(name=algorithm_data.name, key=algorithm_data.key)
                pipeline.algorithms.add(algorithm)

                if created:
                    logger.info(f"Successfully created algorithm {algorithm.name}.")
                    algorithms_created.append(algorithm.name)
                else:
                    logger.info(f"Using existing algorithm {algorithm.name}.")

            for project_data in pipeline_data.projects:
                project, created = Project.objects.get_or_create(name=project_data.name)
                pipeline.projects.add(project)

                if created:
                    logger.info(f"Successfully created project {project.name}.")
                    projects_created.append(project.name)
                else:
                    logger.info(f"Using existing project {project.name}.")

            # @TODO: Add the stages

            pipeline.save()
            pipelines.append(pipeline)

        return PipelineRegistrationResponse(
            timestamp=datetime.datetime.now(),
            success=True,
            pipelines=pipelines_to_add,
            pipelines_created=pipelines_created,
            algorithms_created=algorithms_created,
            projects_created=projects_created,
        )

    def get_status(self):
        info_url = urljoin(self.endpoint_url, "info")
        start_time = time.time()

        resp = requests.get(info_url)
        if not resp.ok:
            try:
                msg = resp.json()["detail"]
            except Exception:
                msg = resp.content

            logger.error(msg)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_checked = timestamp

        pipeline_configs = resp.json() if resp.ok else []
        error = f"{resp.status_code} - {msg}" if not resp.ok else None

        server_live = requests.get(urljoin(self.endpoint_url, "livez")).json().get("status")
        pipelines_online = requests.get(urljoin(self.endpoint_url, "readyz")).json().get("status")
        self.last_checked_live = server_live
        self.save()

        first_response_time = time.time()
        latency = first_response_time - start_time

        response = BackendStatusResponse(
            timestamp=timestamp,
            request_successful=resp.ok,
            server_live=server_live,
            pipelines_online=pipelines_online,
            pipeline_configs=pipeline_configs,
            endpoint_url=self.endpoint_url,
            error=error,
            latency=latency,
        )

        return response
