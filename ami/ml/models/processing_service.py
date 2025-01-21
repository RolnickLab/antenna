import datetime
import logging
import time
import typing
from urllib.parse import urljoin

import requests
from django.db import models

from ami.base.models import BaseModel
from ami.ml.models.pipeline import Pipeline, get_or_create_algorithm_and_category_map
from ami.ml.schemas import PipelineRegistrationResponse, ProcessingServiceInfoResponse, ProcessingServiceStatusResponse

logger = logging.getLogger(__name__)


@typing.final
class ProcessingService(BaseModel):
    """An ML processing service"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    projects = models.ManyToManyField("main.Project", related_name="processing_services", blank=True)
    endpoint_url = models.CharField(max_length=1024)
    pipelines = models.ManyToManyField("ml.Pipeline", related_name="processing_services", blank=True)
    last_checked = models.DateTimeField(null=True)
    last_checked_live = models.BooleanField(null=True)
    last_checked_latency = models.FloatField(null=True)

    def __str__(self):
        return f'#{self.pk} "{self.name}" at {self.endpoint_url}'

    class Meta:
        verbose_name = "Processing Service"
        verbose_name_plural = "Processing Services"

    def create_pipelines(self):
        # Call the status endpoint and get the pipelines/algorithms
        resp = self.get_status()

        pipelines_to_add = resp.pipeline_configs
        pipelines = []
        pipelines_created = []
        algorithms_created = []

        for pipeline_data in pipelines_to_add:
            pipeline, created = Pipeline.objects.get_or_create(
                slug=pipeline_data.slug,
                version=pipeline_data.version,
                defaults={
                    "name": pipeline_data.name,
                    "description": pipeline_data.description or "",
                },
            )
            pipeline.projects.add(*self.projects.all())
            self.pipelines.add(pipeline)

            if created:
                logger.info(f"Successfully created pipeline {pipeline.name}.")
                pipelines_created.append(pipeline.slug)
            else:
                logger.info(f"Using existing pipeline {pipeline.name}.")

            existing_algorithms = pipeline.algorithms.all()
            for algorithm_data in pipeline_data.algorithms:
                algorithm = get_or_create_algorithm_and_category_map(algorithm_data, logger=logger)
                if algorithm not in existing_algorithms:
                    logger.info(f"Registered new algorithm {algorithm.name} to pipeline {pipeline.name}.")
                    pipeline.algorithms.add(algorithm)
                    pipelines_created.append(algorithm.key)
                else:
                    logger.info(f"Using existing algorithm {algorithm.name}.")

            pipeline.save()
            pipelines.append(pipeline)

        return PipelineRegistrationResponse(
            timestamp=datetime.datetime.now(),
            success=True,
            pipelines=pipelines_to_add,
            pipelines_created=pipelines_created,
            algorithms_created=algorithms_created,
        )

    def get_status(self):
        info_url = urljoin(self.endpoint_url, "info")
        start_time = time.time()
        error = None
        timestamp = datetime.datetime.now()
        self.last_checked = timestamp

        try:
            resp = requests.get(info_url)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            latency = time.time() - start_time
            self.last_checked_live = False
            self.last_checked_latency = latency
            self.save()
            error = f"Error connecting to {info_url}: {e}"
            logger.error(error)

            return ProcessingServiceStatusResponse(
                error=error,
                timestamp=timestamp,
                request_successful=False,
                server_live=False,
                pipelines_online=[],
                pipeline_configs=[],
                endpoint_url=self.endpoint_url,
                latency=latency,
            )

        info_data = ProcessingServiceInfoResponse.parse_obj(resp.json())
        pipeline_configs = info_data.pipelines

        # @TODO these are likely extra requests that could be avoided
        # @TODO add schemas for these if we keep them
        server_live: bool = requests.get(urljoin(self.endpoint_url, "livez")).json().get("status", False)
        pipelines_online: list[str] = requests.get(urljoin(self.endpoint_url, "readyz")).json().get("status", [])

        latency = time.time() - start_time
        self.last_checked_live = server_live
        self.last_checked_latency = latency
        self.save()

        response = ProcessingServiceStatusResponse(
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
