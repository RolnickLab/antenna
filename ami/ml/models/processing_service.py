import datetime
import logging
import time
import typing
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.db import models

from ami.base.models import BaseQuerySet
from ami.main.models import BaseModel, Project
from ami.ml.models.pipeline import Pipeline, get_or_create_algorithm_and_category_map
from ami.ml.models.project_pipeline_config import ProjectPipelineConfig
from ami.ml.schemas import (
    PipelineConfigResponse,
    PipelineRegistrationResponse,
    ProcessingServiceInfoResponse,
    ProcessingServiceStatusResponse,
)
from ami.utils.requests import create_session

logger = logging.getLogger(__name__)


class ProcessingServiceQuerySet(BaseQuerySet):
    def async_services(self) -> "ProcessingServiceQuerySet":
        """
        Filter to pull-mode (async) processing services — those with no endpoint URL.

        These correspond to jobs with dispatch_mode=ASYNC_API. Instead of Antenna calling
        out to them, they poll Antenna for tasks and push results back. Their liveness is
        tracked via heartbeats from mark_seen() rather than active health checks.
        """
        return self.filter(models.Q(endpoint_url__isnull=True) | models.Q(endpoint_url__exact=""))

    def sync_services(self) -> "ProcessingServiceQuerySet":
        """
        Filter to push-mode (sync) processing services — those with a configured endpoint URL.

        These correspond to jobs with dispatch_mode=SYNC_API. Antenna actively calls their
        /readyz and /process endpoints. Their liveness is tracked by the periodic
        check_processing_services_online Celery task.
        """
        return self.exclude(models.Q(endpoint_url__isnull=True) | models.Q(endpoint_url__exact=""))


class ProcessingServiceManager(models.Manager.from_queryset(ProcessingServiceQuerySet)):
    """Custom manager for ProcessingService to handle specific queries."""

    def create(self, **kwargs) -> "ProcessingService":
        instance = super().create(**kwargs)
        instance.get_status()  # Check the status of the service immediately after creation
        return instance


@typing.final
class ProcessingService(BaseModel):
    """An ML processing service"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    projects = models.ManyToManyField("main.Project", related_name="processing_services", blank=True)
    endpoint_url = models.CharField(max_length=1024, null=True, blank=True)
    pipelines = models.ManyToManyField("ml.Pipeline", related_name="processing_services", blank=True)
    last_seen = models.DateTimeField(null=True)
    last_seen_live = models.BooleanField(null=True)
    last_seen_latency = models.FloatField(null=True)

    objects = ProcessingServiceManager()

    @property
    def is_async(self) -> bool:
        """
        True if this is a pull-mode (async) service with no endpoint URL, corresponding to
        jobs with dispatch_mode=ASYNC_API. False for push-mode services with a configured
        endpoint, corresponding to jobs with dispatch_mode=SYNC_API.
        """
        return not self.endpoint_url

    def __str__(self):
        endpoint_display = self.endpoint_url or "async"
        return f'#{self.pk} "{self.name}" ({endpoint_display})'

    class Meta:
        verbose_name = "Processing Service"
        verbose_name_plural = "Processing Services"

    def create_pipelines(
        self,
        enable_only: list[str] | None = None,
        projects: models.QuerySet[Project] | None = None,
        pipeline_configs: list[PipelineConfigResponse] | None = None,
    ) -> PipelineRegistrationResponse:
        """
        Register pipeline choices in Antenna using the pipeline configurations from the processing service API.
        """
        pipeline_configs = pipeline_configs or self.get_pipeline_configs()

        pipelines_to_add = pipeline_configs  # all of them
        pipelines = []
        pipelines_created = []
        algorithms_created = []
        projects = projects or self.projects.all()

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

            for project in projects:
                if enable_only is not None and pipeline.slug not in enable_only:
                    enabled = False
                else:
                    enabled = True
                project_pipeline_config, created = ProjectPipelineConfig.objects.get_or_create(
                    pipeline=pipeline,
                    project=project,
                    defaults={"enabled": enabled, "config": {}},
                )
                if created:
                    logger.debug(
                        f"Created project pipeline config for {project.name} and {pipeline.name} (enabled: {enabled})."
                    )
                    project_pipeline_config.save()
                else:
                    logger.debug(f"Using existing project pipeline config for {project.name} and {pipeline.name}.")

            self.pipelines.add(pipeline)

            if created:
                logger.debug(f"Successfully created pipeline {pipeline.name}.")
                pipelines_created.append(pipeline.slug)
            else:
                logger.debug(f"Using existing pipeline {pipeline.name}.")

            existing_algorithms = pipeline.algorithms.all()
            for algorithm_data in pipeline_data.algorithms:
                algorithm = get_or_create_algorithm_and_category_map(algorithm_data, logger=logger)
                if algorithm not in existing_algorithms:
                    logger.debug(f"Registered new algorithm {algorithm.name} to pipeline {pipeline.name}.")
                    pipeline.algorithms.add(algorithm)
                    pipelines_created.append(algorithm.key)
                else:
                    logger.debug(f"Using existing algorithm {algorithm.name}.")

            logger.info(
                f"Pipeline '{pipeline.name}' (slug: {pipeline.slug}, version: {pipeline.version}) "
                f"{'created' if created else 'updated'}, "
                f"applied to {projects.count()} projects. "
                f"pipelines enabled: {enable_only if enable_only else 'all'}"
            )
            pipeline.save()
            pipelines.append(pipeline)

        return PipelineRegistrationResponse(
            timestamp=datetime.datetime.now(),
            success=True,
            pipelines=pipelines_to_add,
            pipelines_created=pipelines_created,
            algorithms_created=algorithms_created,
        )

    def mark_seen(self, live: bool = True) -> None:
        """
        Record that we heard from this processing service.
        Used by async/pull-mode services that don't have an endpoint to check.
        """
        self.last_seen = datetime.datetime.now()
        self.last_seen_live = live
        self.save(update_fields=["last_seen", "last_seen_live"])

    def get_status(self, timeout=90) -> ProcessingServiceStatusResponse:
        """
        Check the status of the processing service.
        This is a simple health check that pings the /readyz endpoint of the service.

        Uses urllib3 Retry with exponential backoff to handle cold starts and transient failures.
        The timeout is set to 90s per attempt to accommodate serverless cold starts, especially for
        services that need to load multiple models into memory. With automatic retries, transient
        connection errors are handled gracefully.

        Args:
            timeout: Request timeout in seconds per attempt (default: 90s for serverless cold starts)
        """
        # If no endpoint URL is configured, return a no-op response
        if self.endpoint_url is None:
            return ProcessingServiceStatusResponse(
                timestamp=datetime.datetime.now(),
                request_successful=False,
                server_live=None,
                pipelines_online=[],
                pipeline_configs=[],
                endpoint_url=self.endpoint_url,
                error="No endpoint URL configured - service operates in pull mode",
                latency=0.0,
            )

        ready_check_url = urljoin(self.endpoint_url, "readyz")
        start_time = time.time()
        error = None
        pipeline_configs = []
        pipelines_online = []
        timestamp = datetime.datetime.now()
        self.last_seen = timestamp
        resp = None

        # Create session with retry logic for connection errors and timeouts
        session = create_session(
            retries=3,
            backoff_factor=2,  # 0s, 2s, 4s delays between retries
            status_forcelist=(500, 502, 503, 504),
        )

        try:
            resp = session.get(ready_check_url, timeout=timeout)
            resp.raise_for_status()
            self.last_seen_live = True
        except requests.exceptions.RequestException as e:
            error = f"Error connecting to {ready_check_url}: {e}"
            logger.error(error)
            self.last_seen_live = False
        finally:
            latency = time.time() - start_time
            self.last_seen_latency = latency
            self.save(
                update_fields=[
                    "last_seen",
                    "last_seen_live",
                    "last_seen_latency",
                ]
            )

        if self.last_seen_live:
            # The specific pipeline statuses are not required for the status response
            # but the intention is to show which ones are loaded into memory and ready to use.
            # @TODO: this may be overkill, but it is displayed in the UI now.
            try:
                assert resp is not None
                pipelines_online: list[str] = resp.json().get("status", [])
            except (ValueError, KeyError) as e:
                error = f"Error parsing pipeline statuses from {ready_check_url}: {e}"
                logger.error(error)

        response = ProcessingServiceStatusResponse(
            timestamp=timestamp,
            request_successful=resp.ok if resp else False,
            server_live=self.last_seen_live,
            pipelines_online=pipelines_online,
            pipeline_configs=pipeline_configs,
            endpoint_url=self.endpoint_url,
            error=error,
            latency=latency,
        )

        return response

    def get_pipeline_configs(self, timeout=6):
        """
        Get the pipeline configurations from the processing service.
        This can be a long response as it includes the full category map for each algorithm.
        """
        if self.endpoint_url is None:
            return []

        info_url = urljoin(self.endpoint_url, "info")
        resp = requests.get(info_url, timeout=timeout)
        resp.raise_for_status()
        info_data = ProcessingServiceInfoResponse.parse_obj(resp.json())
        return info_data.pipelines


def get_or_create_default_processing_service(
    project: "Project",
    register_pipelines: bool = True,
) -> "ProcessingService | None":
    """
    Create a default processing service for a project.

    If configured, will use the global default processing service
    for the current environment. Otherwise, it return None.

    Set the "DEFAULT_PROCESSING_SERVICE_ENDPOINT" and "DEFAULT_PROCESSING_SERVICE_NAME"
    environment variables to configure & enable the default processing service.
    """

    name = settings.DEFAULT_PROCESSING_SERVICE_NAME or "Default Processing Service"
    endpoint_url = settings.DEFAULT_PROCESSING_SERVICE_ENDPOINT
    if not endpoint_url:
        logger.warning(
            "Default processing service is not configured. "
            "Set the 'DEFAULT_PROCESSING_SERVICE_ENDPOINT' environment variable."
        )
        return None

    service, _created = ProcessingService.objects.get_or_create(
        name=name,
        endpoint_url=endpoint_url,
    )
    service.projects.add(project)
    logger.info(f"Created default processing service for project {project}")
    if register_pipelines:
        service.create_pipelines(
            enable_only=settings.DEFAULT_PIPELINES_ENABLED,
            projects=Project.objects.filter(pk=project.pk),
        )
    return service
