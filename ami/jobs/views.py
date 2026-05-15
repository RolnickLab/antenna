import asyncio
import logging

import kombu.exceptions
import nats.errors
from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.db.models import Q
from django.db.models.query import QuerySet
from django.utils import timezone
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import BaseFilterBackend
from rest_framework.response import Response

from ami.base.pagination import LimitOffsetPaginationWithPermissions
from ami.base.permissions import ObjectPermission
from ami.base.serializers import SingleParamSerializer
from ami.base.views import ProjectMixin
from ami.jobs.models import JOB_LOGS_MAX_LIMIT
from ami.jobs.schemas import ids_only_param, incomplete_only_param, logs_limit_param
from ami.jobs.serializers import (
    MLJobResultsRequestSerializer,
    MLJobResultsResponseSerializer,
    MLJobTasksRequestSerializer,
    MLJobTasksResponseSerializer,
)
from ami.jobs.tasks import (
    HEARTBEAT_THROTTLE_SECONDS,
    process_nats_pipeline_result,
    update_async_services_seen_for_pipelines,
    update_async_services_seen_for_project,
    update_pipeline_pull_services_seen,
)
from ami.main.api.schemas import project_id_doc_param
from ami.main.api.views import DefaultViewSet
from ami.utils.fields import url_boolean_param

from .models import Job, JobDispatchMode, JobState
from .serializers import JobListSerializer, JobSerializer, MinimalJobSerializer

logger = logging.getLogger(__name__)


def _actor_log_context(request) -> tuple[str, str | None]:
    """
    Return (user_desc, token_fingerprint) for use in per-job log lines.

    token_fingerprint is the first 8 chars of Token.pk followed by an ellipsis.
    Under DRF TokenAuthentication, Token.pk IS the 40-char bearer secret, so we
    must never write the full value to job logs (readable by all project members).
    Returns None for token_fingerprint when no auth token is present.
    """
    user_desc = getattr(request.user, "email", None) or str(request.user)
    token_id = getattr(request.auth, "pk", None)
    token_fingerprint = f"{str(token_id)[:8]}…" if token_id is not None else None
    return user_desc, token_fingerprint


def _mark_async_services_seen_for_pipelines(pipeline_slugs: tuple[str, ...]) -> None:
    """
    Redis-throttled wrapper around the ``update_async_services_seen_for_pipelines``
    celery task. The wrapper does no DB work itself — it gates dispatch so at
    most one heartbeat is enqueued per sorted slug set per
    ``HEARTBEAT_THROTTLE_SECONDS`` window (currently 30s), keeping the HTTP
    request path cheap under concurrent polling.

    Called from the ``?ids_only=1`` branch of ``JobViewSet.list()`` — the real
    ADC worker shape, which sends ``pipeline__slug__in=<slugs>`` and no
    ``project_id`` (one worker may serve pipelines across many projects and
    has no single project to nominate).
    """
    if not pipeline_slugs:
        return
    cache_key = "heartbeat:list:pipelines:" + ",".join(sorted(pipeline_slugs))
    if not cache.add(cache_key, 1, timeout=HEARTBEAT_THROTTLE_SECONDS):
        return
    try:
        update_async_services_seen_for_pipelines.delay(list(pipeline_slugs))
    except (kombu.exceptions.KombuError, ConnectionError, OSError) as exc:
        logger.warning(f"Failed to enqueue non-critical pipeline-slug heartbeat: {exc}")


def _mark_async_services_seen_for_project(project_id: int) -> None:
    """
    Redis-throttled wrapper around ``update_async_services_seen_for_project``.
    Same shape as ``_mark_async_services_seen_for_pipelines`` above — gates
    celery dispatch to at most one per-project enqueue per
    ``HEARTBEAT_THROTTLE_SECONDS`` window — but keyed by project id for
    callers that send ``?project_id=`` without ``pipeline__slug__in``.

    The ADC worker does not currently use this shape, so this is a fallback.
    Background on why idle-poll heartbeats exist at all: the other heartbeat
    (``_mark_pipeline_pull_services_seen``) only fires from ``/tasks/`` and
    ``/result/`` — i.e., from workers with active work — so a worker sitting
    on ``GET /jobs/?ids_only=1`` between jobs would otherwise age past
    ``PROCESSING_SERVICE_LAST_SEEN_MAX`` and flip to offline in the UI.
    """
    cache_key = f"heartbeat:list:project:{project_id}"
    if not cache.add(cache_key, 1, timeout=HEARTBEAT_THROTTLE_SECONDS):
        return
    try:
        update_async_services_seen_for_project.delay(project_id)
    except (kombu.exceptions.KombuError, ConnectionError, OSError) as exc:
        logger.warning(f"Failed to enqueue non-critical project heartbeat for project {project_id}: {exc}")


def _mark_pipeline_pull_services_seen(job: "Job") -> None:
    """
    Enqueue a fire-and-forget heartbeat for async (pull-mode) processing services
    linked to the job's pipeline.

    A Redis cache gate skips the dispatch when a heartbeat for the same
    (pipeline, project) has already fired within HEARTBEAT_THROTTLE_SECONDS,
    so under concurrent polling we avoid broker + task churn. The Celery task
    keeps the DB write off the HTTP request path.

    Cache key scope: currently `heartbeat:pipeline:<pipeline_id>:project:<project_id>`
    because we cannot yet identify the specific calling service. Once
    application-token auth lands (PR #1117), the key should become
    `heartbeat:service:<service_id>` so each service gets its own throttle
    window and one service's poll does not suppress another's heartbeat.
    """
    if not job.pipeline_id:
        return
    cache_key = f"heartbeat:pipeline:{job.pipeline_id}:project:{job.project_id}"
    if not cache.add(cache_key, 1, timeout=HEARTBEAT_THROTTLE_SECONDS):
        return
    try:
        update_pipeline_pull_services_seen.delay(job.pk)
    except (kombu.exceptions.KombuError, ConnectionError, OSError) as exc:
        msg = f"Failed to enqueue non-critical pipeline heartbeat for job {job.pk}: {exc}"
        logger.warning(msg)
        job.logger.warning(msg)


class JobFilterSet(filters.FilterSet):
    """Custom filterset to enable pipeline name filtering."""

    pipeline__slug = filters.CharFilter(field_name="pipeline__slug", lookup_expr="exact")
    pipeline__slug__in = filters.BaseInFilter(field_name="pipeline__slug", lookup_expr="in")

    class Meta:
        model = Job
        fields = [
            "status",
            "project",
            "deployment",
            "source_image_collection",
            "source_image_single",
            "pipeline",
            "job_type_key",
            "dispatch_mode",
        ]


class IncompleteJobFilter(BaseFilterBackend):
    """Filter backend to filter jobs by incomplete status based on results stage."""

    def filter_queryset(self, request, queryset, view):
        # Check if incomplete_only parameter is set
        incomplete_only = url_boolean_param(request, "incomplete_only", default=False)
        # Filter to incomplete jobs if requested (checks "results" stage status)
        if incomplete_only:
            # Exclude jobs with a terminal top-level status
            queryset = queryset.exclude(status__in=JobState.final_states())

            # Also exclude jobs where the "results" stage has a final state status
            final_states = JobState.final_states()
            exclude_conditions = Q()
            for state in final_states:
                # JSON path query to check if results stage status is in final states
                # @TODO move to a QuerySet method on Job model if/when this needs to be reused elsewhere
                exclude_conditions |= Q(progress__stages__contains=[{"key": "results", "status": state}])

            queryset = queryset.exclude(exclude_conditions)
        return queryset


@extend_schema_view(
    retrieve=extend_schema(parameters=[logs_limit_param]),
)
class JobViewSet(DefaultViewSet, ProjectMixin):
    """
    API endpoint that allows jobs to be viewed or edited.

    Pass the ``start_now`` url parameter to the ``POST`` method to enqueue the job immediately.

    Use the `delay` field to create a test job with fake duration of work (in seconds).

    ## Actions

    ### `/jobs/{id}/run/` (`POST`)

    Run a job (add it to the queue).

    ### `/jobs/{id}/cancel/` (`POST`)

    Cancel a job (terminate the background task)
    """

    queryset = Job.objects.select_related(
        "deployment",
        "pipeline",
        "source_image_collection",
        "source_image_single",
    )
    serializer_class = JobSerializer
    filterset_class = JobFilterSet
    filter_backends = [*DefaultViewSet.filter_backends, IncompleteJobFilter]
    search_fields = ["name", "pipeline__name"]
    ordering_fields = [
        "name",
        "created_at",
        "updated_at",
        "status",
        "started_at",
        "finished_at",
        "project",
        "deployment",
        "source_image_collection",
        "pipeline",
    ]

    permission_classes = [ObjectPermission]

    def get_serializer_class(self):
        """
        Return different serializers for list and detail views.
        """
        if self.action == "list":
            # Use MinimalJobSerializer when ids_only parameter is set
            if url_boolean_param(self.request, "ids_only", default=False):
                return MinimalJobSerializer
            return JobListSerializer
        else:
            return JobSerializer

    def get_serializer_context(self):
        # Validate ``?logs_limit=`` once at the view boundary so a bad value
        # raises DRF ``ValidationError`` (→ HTTP 400) before the serializer
        # runs. ``get_logs`` then reads the cleaned value off context. Pattern
        # mirrors ``ami.base.views.get_active_project`` and the other
        # ``SingleParamSerializer`` callers in ``ami/main/api/views.py``.
        context = super().get_serializer_context()
        if self.action == "retrieve" and self.request is not None:
            context["logs_limit"] = SingleParamSerializer[int].clean(
                param_name="logs_limit",
                field=serializers.IntegerField(required=False, min_value=1, max_value=JOB_LOGS_MAX_LIMIT),
                data=self.request.query_params,
            )
        return context

    @action(detail=True, methods=["post"], name="run")
    def run(self, request, pk=None):
        """
        Run a job (add it to the queue).
        """
        job: Job = self.get_object()

        no_async = url_boolean_param(request, "no_async", default=False)
        if no_async:
            job.run()
        else:
            job.enqueue()
        job.refresh_from_db()
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=["post"], name="retry")
    def retry(self, request, pk=None):
        """
        Re-run a job
        """
        job: Job = self.get_object()
        no_async = url_boolean_param(request, "no_async", default=False)
        if no_async:
            job.retry(async_task=False)
        else:
            job.retry(async_task=True)
        job.refresh_from_db()
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=["post"], name="cancel")
    def cancel(self, request, pk=None):
        """
        Cancel a job (terminate the background task)
        """
        job: Job = self.get_object()
        job.cancel()
        job.refresh_from_db()
        return Response(self.get_serializer(job).data)

    def perform_create(self, serializer):
        """
        If the ``start_now`` parameter is passed, enqueue the job immediately.
        """
        # All jobs created from the Jobs UI are ML jobs.
        # @TODO Remove this when the UI is updated pass a job type
        # Get an instance for the model without saving
        obj = serializer.Meta.model(**serializer.validated_data)
        # Check permissions before saving
        self.check_object_permissions(self.request, obj)

        job: Job = serializer.save()  # type: ignore
        if url_boolean_param(self.request, "start_now", default=False):
            if job.check_custom_permission(self.request.user, "run"):
                # If the user has permission, enqueue the job
                job.enqueue()
            else:
                # If the user does not have permission, raise an error
                raise PermissionDenied("You do not have permission to run this job.")

    def get_queryset(self) -> QuerySet:
        jobs = super().get_queryset()
        project = self.get_active_project()
        if project:
            jobs = jobs.filter(project=project)
        # Validate via SingleParamSerializer so a bad value 400s instead of
        # 500ing through django.forms.IntegerField (raises django.core
        # ValidationError, which DRF's default handler does NOT convert).
        cutoff_hours = SingleParamSerializer[int].clean(
            param_name="cutoff_hours",
            field=serializers.IntegerField(required=False, min_value=0, default=Job.FAILED_JOBS_DISPLAY_MAX_HOURS),
            data=self.request.query_params,
        )
        # Filter out completed jobs that have not been updated in the last X hours
        cutoff_datetime = timezone.now() - timezone.timedelta(hours=cutoff_hours)
        jobs = jobs.exclude(
            status=JobState.failed_states(),
            updated_at__lt=cutoff_datetime,
        )
        # ⚠️ TEMPORARY HACK — remove by 2026-04-24.
        # Worker-polling call path (`ids_only=1`): randomize order so concurrent
        # pollers don't all converge on the same head-of-queue job. An
        # `updated_at`-based sort has a degenerate case at startup — freshly
        # queued jobs all share near-identical timestamps, tie-broken by `pk`,
        # so simultaneous polls deterministically pick the same job. Random
        # ordering gives probabilistic disjoint assignment without writing a
        # poll-stamp column. Combined with `limit=1` below, each poll is an
        # independent "pick any unfinished job" draw.
        #
        # The whole `ids_only=1` branch (this ordering override, the paginator
        # override in `paginator` below, the heartbeat dispatch in `list()`)
        # exists because the ADC worker currently repurposes this list endpoint
        # as a claim-next-job call. Correct shape is a dedicated `/next` action
        # (tracked as #1265). Once `/next` ships
        # and ADC is migrated, delete this `order_by("?")` override along with
        # the paginator override and the list() heartbeat branch.
        if self.action == "list" and url_boolean_param(self.request, "ids_only", default=False):
            jobs = jobs.order_by("?")
        return jobs

    @property
    def paginator(self):
        # ⚠️ TEMPORARY HACK — remove by 2026-04-24.
        # Treat `?ids_only=1` as a pop()-style handoff ("what job is next?")
        # rather than a list() dump: default to one job per response unless the
        # caller explicitly asks for a batch via ?limit=N or ?page_size=N.
        # Concurrent pollers drain a cached list serially and starve later jobs;
        # forcing a re-poll per job lets the random-shuffle fairness sort rotate
        # work across jobs every iteration. No ADC-side change required.
        #
        # This override exists only because `list(ids_only=True)` is being used
        # as a claim-next-job call. Replace with a dedicated `/next` action
        # (tracked as #1265); once ADC is migrated,
        # drop this override so the list endpoint goes back to normal pagination.
        if not hasattr(self, "_paginator"):
            if (
                self.action == "list"
                and url_boolean_param(self.request, "ids_only", default=False)
                and "limit" not in self.request.query_params
                and "page_size" not in self.request.query_params
            ):
                paginator = LimitOffsetPaginationWithPermissions()
                paginator.default_limit = 1
                self._paginator = paginator
            else:
                self._paginator = self.pagination_class() if self.pagination_class is not None else None
        return self._paginator

    @extend_schema(
        parameters=[
            project_id_doc_param,
            ids_only_param,
            incomplete_only_param,
        ]
    )
    def list(self, request, *args, **kwargs):
        # ⚠️ TEMPORARY HACK — remove by 2026-04-24.
        # Worker-polling call path: record heartbeat for async processing services.
        # The real ADC worker request carries ``pipeline__slug__in=...`` and no
        # project_id, so prefer the pipeline-slug scope when those slugs are
        # present; fall back to project scope for callers that pass ?project_id=.
        # Throttled via Redis so concurrent pollers don't churn the DB/broker.
        #
        # This heartbeat branch lives on `list()` only because `list(ids_only=1)`
        # is doubling as the worker's claim-next-job endpoint. Once a dedicated
        # `/next` action ships (tracked as #1265)
        # and ADC is migrated to it, move the heartbeat to that action and
        # delete this branch — `list()` should go back to being a plain list.
        if url_boolean_param(request, "ids_only", default=False):
            pipeline_slugs_raw = request.query_params.get("pipeline__slug__in")
            if pipeline_slugs_raw:
                slugs = tuple(s for s in (p.strip() for p in pipeline_slugs_raw.split(",")) if s)
                _mark_async_services_seen_for_pipelines(slugs)
            else:
                project = self.get_active_project()
                if project is not None:
                    _mark_async_services_seen_for_project(project.pk)
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=MLJobTasksRequestSerializer,
        responses={200: MLJobTasksResponseSerializer},
        parameters=[project_id_doc_param],
    )
    @action(detail=True, methods=["post"], name="tasks")
    def tasks(self, request, pk=None):
        """
        Fetch tasks from the job queue (POST).

        Returns task data with reply_subject for acknowledgment. External workers should:
        1. POST to this endpoint with {"batch_size": N}
        2. Process the tasks
        3. POST to /jobs/{id}/result/ with the results
        """
        serializer = MLJobTasksRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch_size = serializer.validated_data["batch_size"]

        job: Job = self.get_object()

        # Only async_api jobs have tasks fetchable from NATS
        if job.dispatch_mode != JobDispatchMode.ASYNC_API:
            raise ValidationError("Only async_api jobs have fetchable tasks")

        user_desc, token_fingerprint = _actor_log_context(request)

        # Only serve tasks for actively processing jobs. Logging the early-exit
        # makes "phantom-pull" workers (polling against terminal jobs whose NATS
        # stream still exists) visible from the per-job log view.
        if job.status not in JobState.active_states():
            token_suffix = f", token_id={token_fingerprint}" if token_fingerprint is not None else ""
            job.logger.info(
                f"Tasks requested for non-active job (status={job.status}); returning empty. "
                f"user={user_desc}{token_suffix}"
            )
            return Response({"tasks": []})

        # Validate that the job has a pipeline
        if not job.pipeline:
            raise ValidationError("This job does not have a pipeline configured")

        # Record heartbeat for async processing services on this pipeline
        _mark_pipeline_pull_services_seen(job)

        # Get tasks from NATS JetStream
        from ami.ml.orchestration.nats_queue import TaskQueueManager

        async def get_tasks():
            async with TaskQueueManager() as manager:
                return [task.dict() for task in await manager.reserve_tasks(job.pk, count=batch_size, timeout=0.5)]

        try:
            tasks = async_to_sync(get_tasks)()
        except (asyncio.TimeoutError, OSError, nats.errors.Error) as e:
            msg = f"NATS unavailable while fetching tasks for job {job.pk}: {e}"
            logger.warning(msg)
            token_suffix = f", token_id={token_fingerprint}" if token_fingerprint is not None else ""
            job.logger.warning(f"{msg} user={user_desc}{token_suffix}")
            return Response({"error": "Task queue temporarily unavailable"}, status=503)

        token_suffix = f", token_id={token_fingerprint}" if token_fingerprint is not None else ""
        fetch_msg = f"Tasks fetched: requested={batch_size}, delivered={len(tasks)}, user={user_desc}{token_suffix}"
        if len(tasks) > 0:
            job.logger.info(fetch_msg)
        else:
            job.logger.debug(fetch_msg)
        return Response({"tasks": tasks})

    @extend_schema(
        request=MLJobResultsRequestSerializer,
        responses={200: MLJobResultsResponseSerializer},
        parameters=[project_id_doc_param],
    )
    @action(detail=True, methods=["post"], name="result")
    def result(self, request, pk=None):
        """
        Submit pipeline results.

        Accepts: {"results": [PipelineTaskResult, ...]}

        Results are validated then queued for background processing via Celery.
        """

        job = self.get_object()

        # Record heartbeat for async processing services on this pipeline
        _mark_pipeline_pull_services_seen(job)

        user_desc, token_fingerprint = _actor_log_context(request)

        serializer = MLJobResultsRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_results = serializer.validated_data["results"]

        try:
            # All validation passed, now queue all tasks
            queued_tasks = []
            for task_result in validated_results:
                reply_subject = task_result.reply_subject
                result_data = task_result.result

                # Queue the background task
                # Convert Pydantic model to dict for JSON serialization
                task = process_nats_pipeline_result.delay(
                    job_id=job.pk, result_data=result_data.dict(), reply_subject=reply_subject
                )

                queued_tasks.append(
                    {
                        "reply_subject": reply_subject,
                        "status": "queued",
                        "task_id": task.id,
                    }
                )

                logger.info(
                    "Queued pipeline result for job %s, task_id: %s, reply_subject: %s",
                    job.pk,
                    task.id,
                    reply_subject,
                )
                # Mirror to per-job logger so the job log view shows result-POST
                # activity alongside task-fetch activity. Module-logger line above
                # stays for ops-level monitoring outside the per-job context.
                token_suffix = f", token_id={token_fingerprint}" if token_fingerprint is not None else ""
                job.logger.info(
                    f"Queued pipeline result: task_id={task.id}, reply_subject={reply_subject}, "
                    f"user={user_desc}{token_suffix}"
                )

            return Response(
                {
                    "status": "accepted",
                    "job_id": job.pk,
                    "results_queued": len(queued_tasks),
                    "tasks": queued_tasks,
                }
            )

        except (OSError, kombu.exceptions.KombuError) as e:
            logger.error("Failed to queue pipeline results for job %s: %s", job.pk, e)
            return Response(
                {
                    "status": "error",
                    "job_id": job.pk,
                    "detail": "Task queue temporarily unavailable",
                },
                status=503,
            )
