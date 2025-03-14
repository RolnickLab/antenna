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
        """
        Register pipeline choices in Antenna using the pipeline configurations from the processing service API.
        """
        pipeline_configs = self.get_pipeline_configs()

        pipelines_to_add = pipeline_configs  # all of them
        pipelines = []
        pipelines_created = []
        algorithms_created = []

        for pipeline_data in pipelines_to_add:
            pipeline = Pipeline.objects.filter(
                models.Q(slug=pipeline_data.slug) | models.Q(name=pipeline_data.name, version=pipeline_data.version)
            ).first()
            created = False
            if not pipeline:
                pipeline = Pipeline.objects.create(
                    slug=pipeline_data.slug,
                    name=pipeline_data.name,
                    version=pipeline_data.version,
                    description=pipeline_data.description or "",
                )
                created = True

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
        """
        Check the status of the processing service.
        This is a simple health check that pings the /readyz endpoint of the service.
        """
        ready_check_url = urljoin(self.endpoint_url, "readyz")
        start_time = time.time()
        error = None
        pipeline_configs = []
        pipelines_online = []
        timestamp = datetime.datetime.now()
        self.last_checked = timestamp
        resp = None

        try:
            resp = requests.get(ready_check_url)
            resp.raise_for_status()
            self.last_checked_live = True
            latency = time.time() - start_time
        except requests.exceptions.RequestException as e:
            error = f"Error connecting to {ready_check_url}: {e}"
            logger.error(error)
            self.last_checked_live = False
        finally:
            latency = time.time() - start_time
            self.last_checked_latency = latency
            self.save(
                update_fields=[
                    "last_checked",
                    "last_checked_live",
                    "last_checked_latency",
                ]
            )

        if self.last_checked_live:
            # The specific pipeline statuses are not required for the status response
            # but the intention is to show which ones are loaded into memory and ready to use.
            # @TODO: this may be overkill, but it is displayed in the UI now.
            try:
                pipelines_online: list[str] = resp.json().get("status", [])
            except (ValueError, KeyError) as e:
                error = f"Error parsing pipeline statuses from {ready_check_url}: {e}"
                logger.error(error)

        response = ProcessingServiceStatusResponse(
            timestamp=timestamp,
            request_successful=resp.ok if resp else False,
            server_live=self.last_checked_live,
            pipelines_online=pipelines_online,
            pipeline_configs=pipeline_configs,
            endpoint_url=self.endpoint_url,
            error=error,
            latency=latency,
        )

        return response

    def get_pipeline_configs(self):
        """
        Get the pipeline configurations from the processing service.
        This can be a long response as it includes the full category map for each algorithm.
        """
        info_url = urljoin(self.endpoint_url, "info")
        resp = requests.get(info_url)
        resp.raise_for_status()
        info_data = ProcessingServiceInfoResponse.parse_obj(resp.json())
        return info_data.pipelines
