# from rich import print
import logging
from typing import Any

from django.test import TestCase
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase

from ami.base.serializers import reverse_with_params
from ami.jobs.models import (
    Job,
    JobDispatchMode,
    JobLog,
    JobProgress,
    JobState,
    MLJob,
    SourceImageCollectionPopulateJob,
)
from ami.main.models import Project, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.ml.models.processing_service import ProcessingService
from ami.ml.orchestration.jobs import queue_images_to_nats
from ami.users.models import User

logger = logging.getLogger(__name__)


def joined_job_log_messages(job: Job) -> str:
    return "\n".join(JobLog.objects.filter(job=job).order_by("-created_at", "-pk").values_list("message", flat=True))


class TestJobProgress(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Test project")
        self.source_image_collection = SourceImageCollection.objects.create(
            name="Test collection",
            project=self.project,
        )
        self.pipeline = Pipeline.objects.create(
            name="Test ML pipeline",
            description="Test ML pipeline",
        )
        self.pipeline.projects.add(self.project)

    def test_create_job(self):
        job = Job.objects.create(project=self.project, name="Test job - create only")
        self.assertIsInstance(job.progress, JobProgress)
        self.assertEqual(job.progress.summary.progress, 0)
        self.assertEqual(job.progress.stages, [])

    def test_save_does_not_inflate_failed_stage_progress(self):
        """A stage marked FAILURE at partial progress must keep its measured value.

        Regression for the premature ``cleanup_async_job_resources`` path: when a
        worker writes ``status=FAILURE`` at partial progress (e.g. failed/total
        crossed FAILURE_THRESHOLD on an early result), ``Job.update_progress``
        used to coerce ``stage.progress = 1`` on the next save. That made
        ``is_complete()`` return True and triggered cleanup while async results
        were still in flight. Progress is a measurement; leave it alone.
        """
        job = Job.objects.create(project=self.project, name="Test job - partial failure")
        job.progress.add_stage("results")
        job.progress.update_stage("results", progress=0.3, status=JobState.FAILURE)
        job.save()

        results_stage = job.progress.get_stage("results")
        self.assertEqual(results_stage.progress, 0.3)
        self.assertEqual(results_stage.status, JobState.FAILURE)
        self.assertFalse(job.progress.is_complete())

    def test_create_job_with_delay(self):
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job",
            delay=1,
            pipeline=self.pipeline,
            source_image_collection=self.source_image_collection,
        )
        self.assertEqual(job.progress.stages[0].key, "delay")
        self.assertEqual(job.progress.stages[0].progress, 0)
        self.assertEqual(job.progress.stages[0].status, JobState.CREATED)

        self.assertEqual(job.status, JobState.CREATED.value)
        self.assertEqual(job.progress.summary.progress, 0)
        self.assertEqual(job.progress.summary.status, JobState.CREATED)

        job.run()

        self.assertEqual(job.status, JobState.SUCCESS.value)
        self.assertEqual(job.progress.summary.progress, 1)
        self.assertEqual(job.progress.summary.status, JobState.SUCCESS)
        self.assertEqual(job.progress.stages[0].progress, 1)
        self.assertEqual(job.progress.stages[0].status, JobState.SUCCESS)

    def test_job_status_guard_prevents_premature_success(self):
        """
        Test that update_job_status guards against setting SUCCESS
        when job stages are not complete.

        This tests the fix for race conditions where Celery task completes
        but async workers are still processing stages.
        """
        from unittest.mock import Mock

        from ami.jobs.tasks import update_job_status

        # Create job with multiple stages
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job with incomplete stages",
            pipeline=self.pipeline,
            source_image_collection=self.source_image_collection,
        )

        # Add stages that are NOT complete
        job.progress.add_stage("detection")
        job.progress.update_stage("detection", progress=0.5, status=JobState.STARTED)
        job.progress.add_stage("classification")
        job.progress.update_stage("classification", progress=0.0, status=JobState.CREATED)
        job.save()

        # Verify stages are incomplete
        self.assertFalse(job.progress.is_complete())

        # Mock task object
        mock_task = Mock()
        mock_task.request.kwargs = {"job_id": job.pk}
        initial_status = job.status

        # Attempt to set SUCCESS while stages are incomplete
        update_job_status(
            sender=mock_task,
            task_id="test-task-id",
            task=mock_task,
            state=JobState.SUCCESS.value,  # Pass string value, not enum
            retval=None,
        )

        # Verify job status was NOT updated to SUCCESS (should remain CREATED)
        job.refresh_from_db()
        self.assertEqual(job.status, initial_status)
        self.assertNotEqual(job.status, JobState.SUCCESS.value)

    def test_async_job_completes_when_zero_images(self):
        """Job with 0 images to process should finalize immediately, not stay STARTED."""
        from unittest.mock import patch

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test zero images job",
            pipeline=self.pipeline,
            source_image_collection=self.source_image_collection,
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )

        def mock_queue(job, images):
            """Simulate queue_images_to_nats with 0 images: sets stages to SUCCESS, returns True."""
            job.progress.update_stage("process", status=JobState.SUCCESS, progress=1.0)
            job.progress.update_stage("results", status=JobState.SUCCESS, progress=1.0)
            job.save()
            return True

        with (
            patch.object(job.pipeline, "collect_images", return_value=[]),
            patch("ami.ml.orchestration.jobs.queue_images_to_nats", side_effect=mock_queue),
            patch("ami.jobs.tasks.cleanup_async_job_if_needed"),
        ):
            job.run()

        job.refresh_from_db()
        self.assertEqual(job.status, JobState.SUCCESS.value)
        self.assertIsNotNone(job.finished_at)

    def test_job_status_allows_failure_states_immediately(self):
        """
        Test that FAILURE and REVOKED states bypass the completion guard
        and are set immediately regardless of stage completion.
        """
        from unittest.mock import Mock

        from ami.jobs.tasks import update_job_status

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job for failure states",
            pipeline=self.pipeline,
            source_image_collection=self.source_image_collection,
        )

        # Add incomplete stage
        job.progress.add_stage("detection")
        job.progress.update_stage("detection", progress=0.3, status=JobState.STARTED)
        job.save()

        mock_task = Mock()
        mock_task.request.kwargs = {"job_id": job.pk}

        # Test FAILURE state passes through even with incomplete stages
        update_job_status(
            sender=mock_task,
            task_id="test-task-id",
            task=mock_task,
            state=JobState.FAILURE.value,  # Pass string value, not enum
            retval=None,
        )

        job.refresh_from_db()
        self.assertEqual(job.status, JobState.FAILURE.value)


class TestJobView(APITestCase):
    """
    Test the jobs API endpoints.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Jobs Test Project")
        self.test_image = SourceImage.objects.create(path="test.jpg", project=self.project)
        self.source_image_collection = SourceImageCollection.objects.create(
            name="Test collection",
            project=self.project,
        )
        self.source_image_collection.images.add(self.test_image)
        self.job = Job.objects.create(
            job_type_key=SourceImageCollectionPopulateJob.key,
            project=self.project,
            name="Test populate job",
            delay=0,
            source_image_collection=self.source_image_collection,
        )

        self.user = User.objects.create_user(  # type: ignore
            email="testuser@insectai.org",
            is_staff=True,
            is_active=True,
            is_superuser=True,
        )
        self.factory = APIRequestFactory()
        self.pipeline = None  # type: Pipeline | None

    def test_get_job(self):
        self.client.force_authenticate(user=self.user)
        jobs_retrieve_url = reverse_with_params("api:job-detail", args=[self.job.pk])
        resp = self.client.get(jobs_retrieve_url + f"?project_id={self.project.pk}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], self.job.pk)

    def test_get_job_list(self):
        # resp = self.client.get("/api/jobs/")
        jobs_list_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk})
        resp = self.client.get(jobs_list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    def test_create_job_unauthenticated(self):
        jobs_create_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk})
        job_data = {
            "project_id": self.project.pk,
            "source_image_collection_id": self.source_image_collection.pk,
            "name": "Test job unauthenticated",
            "delay": 0,
            "job_type_key": SourceImageCollectionPopulateJob.key,
        }
        self.client.force_authenticate(user=None)
        resp = self.client.post(jobs_create_url, job_data)
        # Accept either 401 (TokenAuthentication) or 403 (SessionAuthentication with AnonymousUser)
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def _create_job(self, name: str, start_now: bool = True):
        jobs_create_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk})

        self.client.force_authenticate(user=self.user)
        job_data = {
            "project_id": self.job.project.pk,
            "name": name,
            "source_image_collection_id": self.source_image_collection.pk,
            "delay": 0,
            "start_now": start_now,
            "job_type_key": SourceImageCollectionPopulateJob.key,
        }
        resp = self.client.post(jobs_create_url, job_data)
        self.client.force_authenticate(user=None)
        self.assertEqual(resp.status_code, 201)
        return resp.json()

    def _create_pipeline(self, name: str = "Test Pipeline", slug: str = "test-pipeline") -> Pipeline:
        """Helper to create a pipeline and add it to the project."""
        if self.pipeline and self.pipeline.slug == slug and self.pipeline.name == name:
            return self.pipeline

        pipeline = Pipeline.objects.create(
            name=name,
            slug=slug,
            description=f"{name} description",
        )
        pipeline.projects.add(self.project)
        self.pipeline = pipeline
        return pipeline

    def _create_ml_job(self, name: str, pipeline: Pipeline) -> Job:
        """Helper to create an ML job with a pipeline."""
        return Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name=name,
            pipeline=pipeline,
            source_image_collection=self.source_image_collection,
        )

    def test_create_job(self):
        job_name = "Test job - Start but don't run"
        data = self._create_job(job_name, start_now=False)
        self.assertEqual(data["project"]["id"], self.project.pk)
        self.assertEqual(data["name"], job_name)

        job = Job.objects.get(pk=data["id"])
        self.assertEqual(job.status, JobState.CREATED.value)

        # @TODO This should be CREATED as well, but it is SUCCESS!
        # progress = JobProgress(**data["progress"])
        # self.assertEqual(progress.summary.status, JobState.CREATED)

    def test_run_job(self):
        data = self._create_job("Test run job", start_now=False)

        job_id = data["id"]
        jobs_run_url = reverse_with_params(
            "api:job-run", args=[job_id], params={"no_async": True, "project_id": self.project.pk}
        )
        self.client.force_authenticate(user=self.user)
        # give user run permission

        assign_perm(Project.Permissions.RUN_POPULATE_CAPTURES_COLLECTION_JOB, self.user, self.project)

        resp = self.client.post(jobs_run_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], job_id)
        self.assertEqual(data["status"], JobState.SUCCESS.value)
        progress = JobProgress(**data["progress"])
        self.assertEqual(progress.summary.status, JobState.SUCCESS)
        self.assertEqual(progress.summary.progress, 1.0)

        # @TODO test async job
        # self.job.refresh_from_db()
        # self.assertIsNotNone(self.job.task_id)

    def test_retry_job(self):
        data = self._create_job("Test retry job", start_now=False)
        job_id = data["id"]
        jobs_retry_url = reverse_with_params(
            "api:job-retry", args=[job_id], params={"no_async": True, "project_id": self.project.pk}
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(jobs_retry_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], job_id)
        self.assertEqual(data["status"], JobState.SUCCESS.value)
        progress = JobProgress(**data["progress"])
        self.assertEqual(progress.summary.status, JobState.SUCCESS)

        # @TODO this should be 1.0, why is the progress object not being properly updated?
        # self.assertEqual(progress.summary.progress, 1.0)

    def test_run_job_unauthenticated(self):
        jobs_run_url = reverse_with_params("api:job-run", args=[self.job.pk], params={"project_id": self.project.pk})
        self.client.force_authenticate(user=None)
        resp = self.client.post(jobs_run_url)
        # Accept either 401 (TokenAuthentication) or 403 (SessionAuthentication with AnonymousUser)
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_cancel_job(self):
        # This cannot be tested until we have a way to cancel jobs
        # and a way to run async tasks in tests.
        pass

    def test_list_jobs_with_ids_only(self):
        """Test the ids_only parameter returns only job IDs."""
        # Create additional jobs via API
        self._create_job("Test job 2", start_now=False)
        self._create_job("Test job 3", start_now=False)

        self.client.force_authenticate(user=self.user)
        # Pass an explicit limit to override the pop()-style default (see test_list_jobs_ids_only_pops_one below).
        jobs_list_url = reverse_with_params(
            "api:job-list",
            params={"project_id": self.project.pk, "ids_only": True, "limit": 10},
        )
        resp = self.client.get(jobs_list_url)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("count", data)
        self.assertEqual(data["count"], 3)  # Original job + 2 new ones
        self.assertEqual(len(data["results"]), 3)
        # Verify these are actually IDs
        self.assertTrue(all(isinstance(r["id"], int) for r in data["results"]))
        # Verify we don't get the full results structure
        self.assertNotIn("details", data["results"][0])

    def test_list_jobs_with_invalid_cutoff_hours_returns_400(self):
        """``?cutoff_hours=abc`` must 400, not 500. Locks in the
        ``SingleParamSerializer`` validation pattern in ``get_queryset``."""
        self.client.force_authenticate(user=self.user)
        url = reverse_with_params(
            "api:job-list",
            params={"project_id": self.project.pk, "cutoff_hours": "abc"},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)

    def test_list_jobs_ids_only_pops_one(self):
        """`?ids_only=1` without an explicit limit returns one job (pop()-style handoff)."""
        self._create_job("Test job 2", start_now=False)
        self._create_job("Test job 3", start_now=False)

        self.client.force_authenticate(user=self.user)
        jobs_list_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk, "ids_only": True})
        resp = self.client.get(jobs_list_url)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["results"]), 1)
        self.assertIsInstance(data["results"][0]["id"], int)

    def test_list_jobs_with_incomplete_only(self):
        """Test the incomplete_only parameter filters jobs correctly."""
        # Create jobs via API
        completed_data = self._create_job("Completed job", start_now=False)
        incomplete_data = self._create_job("Incomplete job", start_now=False)

        # Mark completed job as complete by setting results stage to SUCCESS
        completed_job = Job.objects.get(pk=completed_data["id"])
        completed_job.progress.add_stage("results")
        completed_job.progress.update_stage("results", progress=1.0, status=JobState.SUCCESS)
        completed_job.save()

        # Mark incomplete job as incomplete
        incomplete_job = Job.objects.get(pk=incomplete_data["id"])
        incomplete_job.progress.add_stage("results")
        incomplete_job.progress.update_stage("results", progress=0.5, status=JobState.STARTED)
        incomplete_job.save()

        self.client.force_authenticate(user=self.user)
        jobs_list_url = reverse_with_params(
            "api:job-list", params={"project_id": self.project.pk, "incomplete_only": True}
        )
        resp = self.client.get(jobs_list_url)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Should only return the incomplete job and the original test job (which has no results stage)
        returned_ids = [job["id"] for job in data["results"]]
        self.assertIn(incomplete_job.pk, returned_ids)
        self.assertIn(self.job.pk, returned_ids)  # Original job has no results stage
        self.assertNotIn(completed_job.pk, returned_ids)

    def test_filter_by_pipeline_slug(self):
        """Test filtering jobs by pipeline__slug."""
        pipeline = self._create_pipeline("Test Pipeline", "test-pipeline")
        job_with_pipeline = self._create_ml_job("Job with pipeline", pipeline)

        self.client.force_authenticate(user=self.user)
        jobs_list_url = reverse_with_params(
            "api:job-list", params={"project_id": self.project.pk, "pipeline__slug": "test-pipeline"}
        )
        resp = self.client.get(jobs_list_url)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], job_with_pipeline.pk)

    def test_filter_by_pipeline_slug_in(self):
        """Test filtering jobs by pipeline__slug__in (multiple slugs)."""
        pipeline_a = self._create_pipeline("Pipeline A", "pipeline-a")
        pipeline_b = Pipeline.objects.create(name="Pipeline B", slug="pipeline-b", description="B")
        pipeline_b.projects.add(self.project)
        pipeline_c = Pipeline.objects.create(name="Pipeline C", slug="pipeline-c", description="C")
        pipeline_c.projects.add(self.project)

        job_a = self._create_ml_job("Job A", pipeline_a)
        job_b = self._create_ml_job("Job B", pipeline_b)
        job_c = self._create_ml_job("Job C", pipeline_c)

        self.client.force_authenticate(user=self.user)

        # Filter for two of the three pipelines
        jobs_list_url = reverse_with_params(
            "api:job-list",
            params={"project_id": self.project.pk, "pipeline__slug__in": "pipeline-a,pipeline-b"},
        )
        resp = self.client.get(jobs_list_url)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        returned_ids = {job["id"] for job in data["results"]}
        self.assertIn(job_a.pk, returned_ids)
        self.assertIn(job_b.pk, returned_ids)
        self.assertNotIn(job_c.pk, returned_ids)
        # Original setUp job (no pipeline) should also be excluded
        self.assertNotIn(self.job.pk, returned_ids)

    def test_search_jobs(self):
        """Test searching jobs by name and pipeline name."""
        pipeline = self._create_pipeline("SearchablePipeline", "searchable-pipeline")

        self._create_ml_job("Find me job", pipeline)
        self._create_job("Other job", start_now=False)

        self.client.force_authenticate(user=self.user)

        # Search by job name
        jobs_list_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk, "search": "Find"})
        resp = self.client.get(jobs_list_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertIn("Find me", data["results"][0]["name"])

        # Search by pipeline name
        jobs_list_url = reverse_with_params(
            "api:job-list", params={"project_id": self.project.pk, "search": "Searchable"}
        )
        resp = self.client.get(jobs_list_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["pipeline"]["name"], "SearchablePipeline")

    def _task_batch_helper(self, value: Any, expected_status: int):
        pipeline = self._create_pipeline()
        job = self._create_ml_job("Job for batch test", pipeline)
        job.dispatch_mode = JobDispatchMode.ASYNC_API
        job.status = JobState.STARTED
        job.save(update_fields=["dispatch_mode", "status"])
        images = [
            SourceImage.objects.create(
                path=f"image_{i}.jpg",
                public_base_url="http://example.com",
                project=self.project,
            )
            for i in range(8)  # more than 5 since we test with batch=5
        ]
        queue_images_to_nats(job, images)

        self.client.force_authenticate(user=self.user)
        tasks_url = reverse_with_params("api:job-tasks", args=[job.pk], params={"project_id": self.project.pk})
        resp = self.client.post(tasks_url, {"batch_size": value}, format="json")
        self.assertEqual(resp.status_code, expected_status)
        return resp.json()

    def test_tasks_endpoint_with_batch(self):
        """Test the tasks endpoint respects the batch parameter."""
        data = self._task_batch_helper(5, 200)
        self.assertIn("tasks", data)
        self.assertEqual(len(data["tasks"]), 5)

    def test_tasks_endpoint_with_invalid_batch(self):
        """Test the tasks endpoint with bad batch parameters."""

        for value in ["invalid", None, "", 0]:
            with self.subTest(batch=value):
                self._task_batch_helper(value, 400)

    def test_tasks_endpoint_without_pipeline(self):
        """Test the tasks endpoint returns error when job has no pipeline."""
        # Create a job without a pipeline but with async_api dispatch mode
        # so the dispatch_mode guard passes and the pipeline check is reached
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Job without pipeline",
            source_image_collection=self.source_image_collection,
            dispatch_mode=JobDispatchMode.ASYNC_API,
            status=JobState.STARTED,
        )

        self.client.force_authenticate(user=self.user)
        tasks_url = reverse_with_params("api:job-tasks", args=[job.pk], params={"project_id": self.project.pk})
        resp = self.client.post(tasks_url, {"batch_size": 1}, format="json")

        self.assertEqual(resp.status_code, 400)
        self.assertIn("pipeline", resp.json()[0].lower())

    def test_result_endpoint_stub(self):
        """Test the result endpoint accepts results (stubbed implementation)."""
        pipeline = self._create_pipeline()
        job = self._create_ml_job("Job for results test", pipeline)

        self.client.force_authenticate(user=self.user)
        result_url = reverse_with_params("api:job-result", args=[job.pk], params={"project_id": self.project.pk})

        result_data = {
            "results": [
                {
                    "reply_subject": "test.reply.1",
                    "result": {
                        "pipeline": "test-pipeline",
                        "algorithms": {},
                        "total_time": 1.5,
                        "source_images": [],
                        "detections": [],
                        "errors": None,
                    },
                }
            ]
        }

        resp = self.client.post(result_url, result_data, format="json")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "accepted")
        self.assertEqual(data["job_id"], job.pk)
        self.assertEqual(data["results_queued"], 1)

    def test_result_endpoint_validation(self):
        """Test the result endpoint validates request data."""
        pipeline = self._create_pipeline()
        job = self._create_ml_job("Job for validation test", pipeline)

        self.client.force_authenticate(user=self.user)
        result_url = reverse_with_params("api:job-result", args=[job.pk], params={"project_id": self.project.pk})

        # Test with missing reply_subject
        invalid_data = {"results": [{"result": {"pipeline": "test"}}]}
        resp = self.client.post(result_url, invalid_data, format="json")
        self.assertEqual(resp.status_code, 400)

        # Test with missing result
        invalid_data = {"results": [{"reply_subject": "test.reply"}]}
        resp = self.client.post(result_url, invalid_data, format="json")
        self.assertEqual(resp.status_code, 400)

        # Test with bare list (no longer accepted)
        bare_list = [{"reply_subject": "test.reply", "result": {"pipeline": "test"}}]
        resp = self.client.post(result_url, bare_list, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_tasks_endpoint_logs_fetch_to_job_logger(self):
        """Successful task-fetch lands a 'Tasks fetched' line on the per-job logger."""
        pipeline = self._create_pipeline()
        job = self._create_ml_job("Job for fetch-logging test", pipeline)
        job.dispatch_mode = JobDispatchMode.ASYNC_API
        job.status = JobState.STARTED
        job.save(update_fields=["dispatch_mode", "status"])
        images = [
            SourceImage.objects.create(
                path=f"fetchlog_{i}.jpg",
                public_base_url="http://example.com",
                project=self.project,
            )
            for i in range(3)
        ]
        queue_images_to_nats(job, images)

        self.client.force_authenticate(user=self.user)
        tasks_url = reverse_with_params("api:job-tasks", args=[job.pk], params={"project_id": self.project.pk})
        resp = self.client.post(tasks_url, {"batch_size": 2}, format="json")
        self.assertEqual(resp.status_code, 200)

        job.refresh_from_db()
        joined = joined_job_log_messages(job)
        self.assertIn("Tasks fetched", joined)
        self.assertIn("requested=2", joined)
        self.assertIn("delivered=", joined)
        self.assertIn(self.user.email, joined)

    def test_tasks_endpoint_logs_early_exit_for_terminal_job(self):
        """Polling a terminal-status job produces an empty response and a 'non-active job' log line."""
        pipeline = self._create_pipeline()
        job = self._create_ml_job("Job for early-exit log test", pipeline)
        job.dispatch_mode = JobDispatchMode.ASYNC_API
        job.status = JobState.SUCCESS
        job.save(update_fields=["dispatch_mode", "status"])

        self.client.force_authenticate(user=self.user)
        tasks_url = reverse_with_params("api:job-tasks", args=[job.pk], params={"project_id": self.project.pk})
        resp = self.client.post(tasks_url, {"batch_size": 5}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"tasks": []})

        job.refresh_from_db()
        joined = joined_job_log_messages(job)
        self.assertIn("non-active job", joined)
        self.assertIn(f"status={JobState.SUCCESS}", joined)

    def test_result_endpoint_mirrors_queued_log_to_job_logger(self):
        """The result endpoint mirrors its 'Queued pipeline result' line to the per-job logger."""
        from unittest.mock import MagicMock, patch

        pipeline = self._create_pipeline()
        job = self._create_ml_job("Job for result-logging test", pipeline)

        self.client.force_authenticate(user=self.user)
        result_url = reverse_with_params("api:job-result", args=[job.pk], params={"project_id": self.project.pk})

        result_data = {
            "results": [
                {
                    "reply_subject": "test.reply.logged",
                    "result": {
                        "pipeline": "test-pipeline",
                        "algorithms": {},
                        "total_time": 0.1,
                        "source_images": [],
                        "detections": [],
                        "errors": None,
                    },
                }
            ]
        }

        # Keep the Celery task from actually running; the log line is emitted
        # by the view before delegating to Celery.
        mock_async_result = MagicMock()
        mock_async_result.id = "mirrored-task-id"
        with patch("ami.jobs.views.process_nats_pipeline_result.delay", return_value=mock_async_result):
            resp = self.client.post(result_url, result_data, format="json")
        self.assertEqual(resp.status_code, 200)

        job.refresh_from_db()
        joined = joined_job_log_messages(job)
        self.assertIn("Queued pipeline result", joined)
        self.assertIn("mirrored-task-id", joined)
        self.assertIn("test.reply.logged", joined)
        self.assertIn(self.user.email, joined)

    def test_tasks_fetch_log_uses_token_fingerprint_not_full_token(self):
        """
        Fix 1: token written to per-job logs is truncated to 8 chars + ellipsis,
        never the full 40-char DRF bearer secret.
        """
        from rest_framework.authtoken.models import Token

        pipeline = self._create_pipeline()
        job = self._create_ml_job("Job for token-fingerprint test", pipeline)
        job.dispatch_mode = JobDispatchMode.ASYNC_API
        job.status = JobState.STARTED
        job.save(update_fields=["dispatch_mode", "status"])
        images = [
            SourceImage.objects.create(
                path=f"tokentest_{i}.jpg",
                public_base_url="http://example.com",
                project=self.project,
            )
            for i in range(2)
        ]
        queue_images_to_nats(job, images)

        token, _ = Token.objects.get_or_create(user=self.user)
        # Authenticate with the actual token object so request.auth.pk is set
        self.client.force_authenticate(user=self.user, token=token)

        tasks_url = reverse_with_params("api:job-tasks", args=[job.pk], params={"project_id": self.project.pk})
        resp = self.client.post(tasks_url, {"batch_size": 2}, format="json")
        self.assertEqual(resp.status_code, 200)

        job.refresh_from_db()
        joined = joined_job_log_messages(job)
        # Full token key must NOT appear anywhere in logs
        self.assertNotIn(token.key, joined)
        # Fingerprint (first 8 chars + ellipsis) MUST appear
        expected_fingerprint = f"{token.key[:8]}…"
        self.assertIn(expected_fingerprint, joined)

    def test_tasks_fetch_zero_delivered_does_not_log_to_stdout(self):
        """
        Fix 2: when delivered==0, the log line is emitted at DEBUG and must not
        land in job.logs.stdout (JobLogHandler only captures INFO and above).
        """
        pipeline = self._create_pipeline()
        job = self._create_ml_job("Job for zero-delivered test", pipeline)
        job.dispatch_mode = JobDispatchMode.ASYNC_API
        job.status = JobState.STARTED
        job.save(update_fields=["dispatch_mode", "status"])
        # Do NOT queue any images — NATS will return 0 tasks.

        self.client.force_authenticate(user=self.user)
        tasks_url = reverse_with_params("api:job-tasks", args=[job.pk], params={"project_id": self.project.pk})
        resp = self.client.post(tasks_url, {"batch_size": 5}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["tasks"]), 0)

        job.refresh_from_db()
        # No Tasks fetched line should appear in stdout for a zero-delivery poll
        joined = joined_job_log_messages(job)
        self.assertNotIn("Tasks fetched", joined)

    def test_tasks_fetch_nonzero_delivered_logs_to_stdout(self):
        """
        Fix 2: when delivered>0, the log line is emitted at INFO and lands in
        job.logs.stdout with the correct delivered count.
        """
        pipeline = self._create_pipeline()
        job = self._create_ml_job("Job for nonzero-delivered test", pipeline)
        job.dispatch_mode = JobDispatchMode.ASYNC_API
        job.status = JobState.STARTED
        job.save(update_fields=["dispatch_mode", "status"])
        images = [
            SourceImage.objects.create(
                path=f"nonzero_{i}.jpg",
                public_base_url="http://example.com",
                project=self.project,
            )
            for i in range(3)
        ]
        queue_images_to_nats(job, images)

        self.client.force_authenticate(user=self.user)
        tasks_url = reverse_with_params("api:job-tasks", args=[job.pk], params={"project_id": self.project.pk})
        resp = self.client.post(tasks_url, {"batch_size": 3}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["tasks"]), 3)

        job.refresh_from_db()
        joined = joined_job_log_messages(job)
        self.assertIn("Tasks fetched", joined)
        self.assertIn("delivered=3", joined)


class TestJobThroughputLogging(TestCase):
    """Unit tests for _log_job_throughput (Task 3)."""

    def setUp(self):
        self.project = Project.objects.create(name="Throughput Test Project")
        self.pipeline = Pipeline.objects.create(name="Throughput Pipeline", slug="throughput-pipeline")
        self.pipeline.projects.add(self.project)
        self.job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Throughput job",
            pipeline=self.pipeline,
        )

    def _seed_process_stage(self, processed: int, remaining: int) -> None:
        self.job.progress.add_stage("process")
        self.job.progress.update_stage(
            "process",
            progress=processed / max(1, processed + remaining),
            status=JobState.STARTED,
            processed=processed,
            remaining=remaining,
            failed=0,
        )
        self.job.save()

    def test_throughput_line_is_well_formed(self):
        import datetime

        from ami.jobs.tasks import _log_job_throughput

        self._seed_process_stage(processed=10, remaining=90)
        self.job.started_at = datetime.datetime.now() - datetime.timedelta(minutes=5)
        self.job.save(update_fields=["started_at"])

        _log_job_throughput(self.job, "process")

        self.job.refresh_from_db()
        joined = joined_job_log_messages(self.job)
        self.assertIn("throughput", joined)
        self.assertIn("processed=10/100", joined)
        self.assertIn("rate=2.0 imgs/min", joined)
        # ETA for 90 remaining at 2.0 imgs/min = 45 minutes
        self.assertIn("ETA=45m", joined)

    def test_throughput_skipped_when_started_at_is_none(self):
        from ami.jobs.tasks import _log_job_throughput

        self._seed_process_stage(processed=5, remaining=5)
        self.assertIsNone(self.job.started_at)

        _log_job_throughput(self.job, "process")

        self.job.refresh_from_db()
        joined = joined_job_log_messages(self.job)
        self.assertNotIn("throughput", joined)

    def test_throughput_skipped_for_non_processing_stage(self):
        import datetime

        from ami.jobs.tasks import _log_job_throughput

        self._seed_process_stage(processed=10, remaining=90)
        self.job.started_at = datetime.datetime.now() - datetime.timedelta(minutes=5)
        self.job.save(update_fields=["started_at"])

        _log_job_throughput(self.job, "delay")

        self.job.refresh_from_db()
        joined = joined_job_log_messages(self.job)
        self.assertNotIn("throughput", joined)

    def test_throughput_with_zero_processed_reports_unknown_eta(self):
        import datetime

        from ami.jobs.tasks import _log_job_throughput

        self._seed_process_stage(processed=0, remaining=50)
        self.job.started_at = datetime.datetime.now() - datetime.timedelta(minutes=5)
        self.job.save(update_fields=["started_at"])

        _log_job_throughput(self.job, "process")

        self.job.refresh_from_db()
        joined = joined_job_log_messages(self.job)
        self.assertIn("processed=0/50", joined)
        self.assertIn("rate=0.0", joined)
        self.assertIn("ETA=unknown", joined)


class TestJobLogPersistence(TestCase):
    """Exercise the JobLog table / legacy-JSON fallback paths on JobLogHandler.emit."""

    def setUp(self):
        self.project = Project.objects.create(name="JobLog Test Project")
        self.pipeline = Pipeline.objects.create(name="JobLog Pipeline", slug="joblog-pipeline")
        self.pipeline.projects.add(self.project)
        self.job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="JobLog emit test job",
            pipeline=self.pipeline,
        )

    def test_emit_inserts_one_joblog_row_per_call(self):
        self.job.logger.info("first")
        self.job.logger.error("boom")

        rows = list(JobLog.objects.filter(job=self.job).order_by("pk").values("level", "message"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["level"], "INFO")
        self.assertIn("first", rows[0]["message"])
        self.assertEqual(rows[1]["level"], "ERROR")
        self.assertIn("boom", rows[1]["message"])

        # emit must not repopulate the legacy JSON column.
        self.job.refresh_from_db(fields=["logs"])
        self.assertEqual(self.job.logs.stdout, [])
        self.assertEqual(self.job.logs.stderr, [])

    def test_flag_disabled_short_circuits_emit(self):
        from django.test import override_settings

        with override_settings(JOB_LOG_PERSIST_ENABLED=False):
            self.job.logger.info("suppressed")
            self.job.logger.error("also suppressed")

        self.assertFalse(JobLog.objects.filter(job=self.job).exists())
        self.job.refresh_from_db(fields=["logs"])
        self.assertEqual(self.job.logs.stdout, [])
        self.assertEqual(self.job.logs.stderr, [])

    def test_serialize_job_logs_reads_from_joblog_table(self):
        from ami.jobs.serializers import serialize_job_logs

        self.job.logger.info("hello world")
        self.job.logger.error("something failed")

        logs = serialize_job_logs(self.job)

        self.assertEqual(len(logs["stdout"]), 2)
        # Newest-first ordering.
        self.assertIn("ERROR", logs["stdout"][0])
        self.assertIn("something failed", logs["stdout"][0])
        self.assertIn("INFO", logs["stdout"][1])
        self.assertIn("hello world", logs["stdout"][1])
        self.assertEqual(logs["stderr"], ["something failed"])

    def test_serialize_job_logs_falls_back_to_legacy_json(self):
        """A job with no JobLog rows but a populated ``logs`` JSON column (a
        pre-migration job, or a job written under ``JOB_LOG_PERSIST_ENABLED=False``
        after legacy data had been seeded) still renders through the serializer."""
        from ami.jobs.models import JobLogs as JobLogsSchema
        from ami.jobs.serializers import serialize_job_logs

        self.job.logs = JobLogsSchema(stdout=["[2025-01-01 00:00:00] INFO legacy line"], stderr=["old error"])
        self.job.save(update_fields=["logs"])
        self.assertFalse(JobLog.objects.filter(job=self.job).exists())

        logs = serialize_job_logs(self.job)

        self.assertEqual(logs["stdout"], ["[2025-01-01 00:00:00] INFO legacy line"])
        self.assertEqual(logs["stderr"], ["old error"])

    def test_get_logs_list_action_skips_joblog_query(self):
        """The ``get_logs`` method on JobListSerializer returns the legacy JSON
        shape when the viewset action is ``list``. This avoids N+1 on joined
        log rows and matches UI expectations (the list view does not render logs)."""
        from unittest.mock import MagicMock

        from ami.jobs.models import JobLogs as JobLogsSchema
        from ami.jobs.serializers import JobListSerializer

        self.job.logger.info("ignored in list view")
        self.assertEqual(JobLog.objects.filter(job=self.job).count(), 1)

        self.job.logs = JobLogsSchema(stdout=["legacy-only"], stderr=[])
        self.job.save(update_fields=["logs"])

        # Directly instantiate the serializer with a fake view context claiming
        # the list action; confirms list responses do not hit JobLog rows.
        fake_view = MagicMock()
        fake_view.action = "list"
        serializer = JobListSerializer(instance=self.job, context={"view": fake_view})
        logs = serializer.get_logs(self.job)

        self.assertEqual(logs["stdout"], ["legacy-only"])
        self.assertEqual(logs["stderr"], [])

    def test_get_logs_detail_action_reads_joblog_table(self):
        from unittest.mock import MagicMock

        from ami.jobs.serializers import JobListSerializer

        self.job.logger.info("detail view reads me")

        fake_view = MagicMock()
        fake_view.action = "retrieve"
        serializer = JobListSerializer(instance=self.job, context={"view": fake_view})
        logs = serializer.get_logs(self.job)

        self.assertEqual(len(logs["stdout"]), 1)
        self.assertIn("detail view reads me", logs["stdout"][0])

    def _make_detail_serializer(self, logs_limit: int | None = None):
        # Mirror what JobViewSet.get_serializer_context produces for a
        # detail (retrieve) action: ``logs_limit`` is the validated int (or
        # None when the param was not passed).
        from unittest.mock import MagicMock

        from ami.jobs.serializers import JobListSerializer

        fake_view = MagicMock()
        fake_view.action = "retrieve"
        return JobListSerializer(
            instance=self.job,
            context={"view": fake_view, "logs_limit": logs_limit},
        )

    def test_logs_limit_caps_response_size(self):
        for i in range(5):
            self.job.logger.info(f"line {i}")
        self.assertEqual(JobLog.objects.filter(job=self.job).count(), 5)

        serializer = self._make_detail_serializer(logs_limit=2)
        logs = serializer.get_logs(self.job)

        self.assertEqual(len(logs["stdout"]), 2)
        # Newest-first.
        self.assertIn("line 4", logs["stdout"][0])
        self.assertIn("line 3", logs["stdout"][1])

    def test_logs_limit_default_when_unset(self):
        from ami.jobs.models import JOB_LOGS_DEFAULT_LIMIT

        self.job.logger.info("only one")

        serializer = self._make_detail_serializer(logs_limit=None)
        logs = serializer.get_logs(self.job)

        # Default kicks in (no truncation; 1 < 1000).
        self.assertEqual(len(logs["stdout"]), 1)
        self.assertGreaterEqual(JOB_LOGS_DEFAULT_LIMIT, 1)


class TestJobLogsLimitHTTPValidation(APITestCase):
    """``?logs_limit=`` validation runs at the view boundary, so a bad value
    must produce HTTP 400 (not 500). Validated via the actual API path rather
    than calling the serializer directly."""

    def setUp(self):
        self.project = Project.objects.create(name="logs_limit HTTP test")
        self.job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="logs_limit HTTP test job",
        )
        self.user = User.objects.create_user(  # type: ignore
            email="logs-limit-validator@insectai.org",
            is_staff=True,
            is_active=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.user)

    def _detail_url(self, **params) -> str:
        return reverse_with_params("api:job-detail", args=[self.job.pk], params=params)

    def test_valid_integer_returns_200(self):
        # Sanity: a well-formed ``?logs_limit=`` does not 400 on its own.
        resp = self.client.get(self._detail_url(project_id=self.project.pk, logs_limit=5))
        self.assertEqual(resp.status_code, 200)

    def test_non_integer_returns_400(self):
        resp = self.client.get(self._detail_url(project_id=self.project.pk, logs_limit="abc"))
        self.assertEqual(resp.status_code, 400)

    def test_zero_returns_400(self):
        resp = self.client.get(self._detail_url(project_id=self.project.pk, logs_limit=0))
        self.assertEqual(resp.status_code, 400)

    def test_negative_returns_400(self):
        resp = self.client.get(self._detail_url(project_id=self.project.pk, logs_limit=-5))
        self.assertEqual(resp.status_code, 400)

    def test_above_max_returns_400(self):
        from ami.jobs.models import JOB_LOGS_MAX_LIMIT

        resp = self.client.get(self._detail_url(project_id=self.project.pk, logs_limit=JOB_LOGS_MAX_LIMIT + 1))
        self.assertEqual(resp.status_code, 400)


class TestJobDispatchModeFiltering(APITestCase):
    """Test job filtering by dispatch_mode."""

    def setUp(self):
        self.user = User.objects.create_user(  # type: ignore
            email="testuser-backend@insectai.org",
            is_staff=True,
            is_active=True,
            is_superuser=True,
        )
        self.project = Project.objects.create(name="Test Backend Project")

        # Create pipeline for ML jobs
        self.pipeline = Pipeline.objects.create(
            name="Test ML Pipeline",
            slug="test-ml-pipeline",
            description="Test ML pipeline for dispatch_mode filtering",
        )
        self.pipeline.projects.add(self.project)

        # Create source image collection for jobs
        self.source_image_collection = SourceImageCollection.objects.create(
            name="Test Collection",
            project=self.project,
        )

        # Give the user necessary permissions
        assign_perm(Project.Permissions.VIEW_PROJECT, self.user, self.project)

    def test_dispatch_mode_filtering(self):
        """Test that jobs can be filtered by dispatch_mode parameter."""
        # Create two ML jobs with different dispatch modes
        sync_job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Sync API Job",
            pipeline=self.pipeline,
            source_image_collection=self.source_image_collection,
            dispatch_mode=JobDispatchMode.SYNC_API,
        )

        async_job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Async API Job",
            pipeline=self.pipeline,
            source_image_collection=self.source_image_collection,
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )

        # Create a non-ML job without a pipeline (dispatch_mode stays "internal")
        internal_job = Job.objects.create(
            job_type_key="data_storage_sync",
            project=self.project,
            name="Internal Job",
        )

        self.client.force_authenticate(user=self.user)
        jobs_list_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk})

        # Test filtering by sync_api dispatch_mode
        resp = self.client.get(jobs_list_url, {"dispatch_mode": JobDispatchMode.SYNC_API})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], sync_job.pk)
        self.assertEqual(data["results"][0]["dispatch_mode"], JobDispatchMode.SYNC_API)

        # Test filtering by async_api dispatch_mode
        resp = self.client.get(jobs_list_url, {"dispatch_mode": JobDispatchMode.ASYNC_API})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], async_job.pk)
        self.assertEqual(data["results"][0]["dispatch_mode"], JobDispatchMode.ASYNC_API)

        # Test filtering by invalid dispatch_mode (should return 400 due to choices validation)
        resp = self.client.get(jobs_list_url, {"dispatch_mode": "non_existent_mode"})
        self.assertEqual(resp.status_code, 400)

        # Test without dispatch_mode filter (should return all jobs)
        resp = self.client.get(jobs_list_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 3)  # All three jobs

        # Verify the job IDs returned include all jobs
        returned_ids = {job["id"] for job in data["results"]}
        expected_ids = {sync_job.pk, async_job.pk, internal_job.pk}
        self.assertEqual(returned_ids, expected_ids)

    def test_ml_job_dispatch_mode_set_on_creation(self):
        """Test that ML jobs get dispatch_mode set based on project feature flags at creation time."""
        # Without async flag, ML job should default to sync_api
        sync_job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Auto Sync Job",
            pipeline=self.pipeline,
            source_image_collection=self.source_image_collection,
        )
        self.assertEqual(sync_job.dispatch_mode, JobDispatchMode.SYNC_API)

        # Enable async flag on project
        self.project.feature_flags.async_pipeline_workers = True
        self.project.save()

        async_job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Auto Async Job",
            pipeline=self.pipeline,
            source_image_collection=self.source_image_collection,
        )
        self.assertEqual(async_job.dispatch_mode, JobDispatchMode.ASYNC_API)

        # Non-pipeline job should stay internal regardless of feature flag
        internal_job = Job.objects.create(
            job_type_key="data_storage_sync",
            project=self.project,
            name="Internal Job",
        )
        self.assertEqual(internal_job.dispatch_mode, JobDispatchMode.INTERNAL)

    def test_tasks_endpoint_rejects_non_async_jobs(self):
        """Test that /tasks endpoint returns 400 for non-async_api jobs."""
        from ami.base.serializers import reverse_with_params

        sync_job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Sync Job for tasks test",
            pipeline=self.pipeline,
            source_image_collection=self.source_image_collection,
            dispatch_mode=JobDispatchMode.SYNC_API,
        )

        self.client.force_authenticate(user=self.user)
        tasks_url = reverse_with_params("api:job-tasks", args=[sync_job.pk], params={"project_id": self.project.pk})
        resp = self.client.post(tasks_url, {"batch_size": 1}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("async_api", resp.json()[0].lower())


class TestPipelineHeartbeatTask(APITestCase):
    """
    Unit tests for update_pipeline_pull_services_seen and the view-level
    _mark_pipeline_pull_services_seen fire-and-forget dispatch.
    """

    def setUp(self):
        from django.core.cache import cache

        # Cache-based gate in _mark_pipeline_pull_services_seen would otherwise
        # carry over between tests and suppress the .delay() we want to assert.
        cache.clear()

        self.project = Project.objects.create(name="Heartbeat Test Project")
        self.pipeline = Pipeline.objects.create(name="Heartbeat Pipeline", slug="heartbeat-pipeline")
        self.pipeline.projects.add(self.project)
        self.collection = SourceImageCollection.objects.create(name="HB Collection", project=self.project)
        self.job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Heartbeat Test Job",
            pipeline=self.pipeline,
            source_image_collection=self.collection,
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )
        self.service = ProcessingService.objects.create(
            name="Heartbeat Worker",
            endpoint_url=None,  # None = pull-mode / async service
        )
        self.service.pipelines.add(self.pipeline)
        self.service.projects.add(self.project)

    def test_tasks_endpoint_dispatches_heartbeat_task(self):
        """The /tasks endpoint calls update_pipeline_pull_services_seen.delay(), not the DB directly."""
        from unittest.mock import patch

        job = self.job
        job.status = JobState.STARTED
        job.save(update_fields=["status"])

        images = [
            SourceImage.objects.create(
                path=f"hb_tasks_{i}.jpg",
                public_base_url="http://example.com",
                project=self.project,
            )
            for i in range(2)
        ]
        queue_images_to_nats(job, images)

        user = User.objects.create_user(email="hbtest@example.com", is_superuser=True, is_active=True)
        self.client.force_authenticate(user=user)

        with patch("ami.jobs.views.update_pipeline_pull_services_seen.delay") as mock_delay:
            tasks_url = reverse_with_params("api:job-tasks", args=[job.pk], params={"project_id": self.project.pk})
            resp = self.client.post(tasks_url, {"batch_size": 1}, format="json")

        self.assertEqual(resp.status_code, 200)
        mock_delay.assert_called_once_with(job.pk)

    def test_result_endpoint_dispatches_heartbeat_task(self):
        """The /result endpoint calls update_pipeline_pull_services_seen.delay(), not the DB directly."""
        from unittest.mock import MagicMock, patch

        user = User.objects.create_user(email="hbresult@example.com", is_superuser=True, is_active=True)
        self.client.force_authenticate(user=user)

        result_data = {
            "results": [
                {
                    "reply_subject": "test.reply.hb",
                    "result": {
                        "pipeline": "heartbeat-pipeline",
                        "algorithms": {},
                        "total_time": 0.1,
                        "source_images": [],
                        "detections": [],
                        "errors": None,
                    },
                }
            ]
        }

        mock_async_result = MagicMock()
        mock_async_result.id = "hb-task-id"
        with (
            patch("ami.jobs.views.process_nats_pipeline_result.delay", return_value=mock_async_result),
            patch("ami.jobs.views.update_pipeline_pull_services_seen.delay") as mock_delay,
        ):
            result_url = reverse_with_params(
                "api:job-result", args=[self.job.pk], params={"project_id": self.project.pk}
            )
            resp = self.client.post(result_url, result_data, format="json")

        self.assertEqual(resp.status_code, 200)
        mock_delay.assert_called_once_with(self.job.pk)

    def test_tasks_endpoint_tolerates_heartbeat_dispatch_failure(self):
        """Heartbeat enqueue errors should not fail the /tasks response."""
        from unittest.mock import patch

        from kombu.exceptions import OperationalError

        job = self.job
        job.status = JobState.STARTED
        job.save(update_fields=["status"])

        image = SourceImage.objects.create(
            path="hb_tasks_broker.jpg",
            public_base_url="http://example.com",
            project=self.project,
        )
        queue_images_to_nats(job, [image])

        user = User.objects.create_user(email="hbbroker@example.com", is_superuser=True, is_active=True)
        self.client.force_authenticate(user=user)

        with patch(
            "ami.jobs.views.update_pipeline_pull_services_seen.delay",
            side_effect=OperationalError("broker unavailable"),
        ):
            tasks_url = reverse_with_params("api:job-tasks", args=[job.pk], params={"project_id": self.project.pk})
            resp = self.client.post(tasks_url, {"batch_size": 1}, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["tasks"]), 1)

    def test_view_gate_suppresses_redundant_dispatches(self):
        """Rapid repeated calls to _mark_pipeline_pull_services_seen should only enqueue once per window."""
        from unittest.mock import patch

        from ami.jobs.views import _mark_pipeline_pull_services_seen

        with patch("ami.jobs.views.update_pipeline_pull_services_seen.delay") as mock_delay:
            for _ in range(5):
                _mark_pipeline_pull_services_seen(self.job)

        self.assertEqual(mock_delay.call_count, 1)


class TestListEndpointHeartbeat(APITestCase):
    """
    Unit tests for _mark_async_services_seen_for_project and the list endpoint's
    heartbeat dispatch on ``?ids_only=1`` polls.
    """

    def setUp(self):
        from django.core.cache import cache

        cache.clear()

        self.project = Project.objects.create(name="List Heartbeat Project")
        self.service = ProcessingService.objects.create(
            name="List Heartbeat Worker",
            endpoint_url=None,
        )
        self.service.projects.add(self.project)

        self.user = User.objects.create_user(email="list-heartbeat@example.com", is_superuser=True, is_active=True)
        self.client.force_authenticate(user=self.user)

    def test_list_with_ids_only_dispatches_heartbeat(self):
        from unittest.mock import patch

        list_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk, "ids_only": True})
        with patch("ami.jobs.views.update_async_services_seen_for_project.delay") as mock_delay:
            resp = self.client.get(list_url)

        self.assertEqual(resp.status_code, 200)
        mock_delay.assert_called_once_with(self.project.pk)

    def test_list_without_ids_only_does_not_dispatch_heartbeat(self):
        from unittest.mock import patch

        list_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk})
        with patch("ami.jobs.views.update_async_services_seen_for_project.delay") as mock_delay:
            resp = self.client.get(list_url)

        self.assertEqual(resp.status_code, 200)
        mock_delay.assert_not_called()

    def test_list_heartbeat_tolerates_dispatch_failure(self):
        """Broker unavailability on heartbeat enqueue must not break the list response."""
        from unittest.mock import patch

        from kombu.exceptions import OperationalError

        list_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk, "ids_only": True})
        with patch(
            "ami.jobs.views.update_async_services_seen_for_project.delay",
            side_effect=OperationalError("broker unavailable"),
        ):
            resp = self.client.get(list_url)

        self.assertEqual(resp.status_code, 200)

    def test_view_gate_suppresses_redundant_list_dispatches(self):
        """Rapid repeated list polls should dispatch at most once per throttle window."""
        from unittest.mock import patch

        from ami.jobs.views import _mark_async_services_seen_for_project

        with patch("ami.jobs.views.update_async_services_seen_for_project.delay") as mock_delay:
            for _ in range(5):
                _mark_async_services_seen_for_project(self.project.pk)

        self.assertEqual(mock_delay.call_count, 1)

    def test_list_with_pipeline_slugs_no_project_dispatches_heartbeat(self):
        """Real ADC worker shape: ?ids_only=1&pipeline__slug__in=... with no project_id."""
        from unittest.mock import patch

        pipeline = Pipeline.objects.create(name="Heartbeat Pipeline", slug="heartbeat-pipeline")
        self.service.pipelines.add(pipeline)

        list_url = reverse_with_params(
            "api:job-list",
            params={"ids_only": True, "pipeline__slug__in": "heartbeat-pipeline"},
        )
        with patch("ami.jobs.views.update_async_services_seen_for_pipelines.delay") as mock_delay:
            resp = self.client.get(list_url)

        self.assertEqual(resp.status_code, 200)
        mock_delay.assert_called_once_with(["heartbeat-pipeline"])

    def test_task_updates_services_via_pipeline_slug(self):
        """The pipeline-slug celery task marks matching async services live."""
        import datetime

        from ami.jobs.tasks import update_async_services_seen_for_pipelines

        pipeline = Pipeline.objects.create(name="Slug Pipeline", slug="slug-pipeline")
        self.service.pipelines.add(pipeline)
        unrelated = ProcessingService.objects.create(name="Unrelated Async", endpoint_url=None)
        unrelated_last_seen_before = unrelated.last_seen

        before = datetime.datetime.now() - datetime.timedelta(seconds=1)
        update_async_services_seen_for_pipelines(["slug-pipeline"])

        self.service.refresh_from_db()
        unrelated.refresh_from_db()

        self.assertTrue(self.service.last_seen_live)
        self.assertIsNotNone(self.service.last_seen)
        self.assertGreaterEqual(self.service.last_seen, before)
        self.assertEqual(unrelated.last_seen, unrelated_last_seen_before)

    def test_task_updates_all_project_async_services(self):
        """The celery task marks every async service on the project live."""
        import datetime

        from ami.jobs.tasks import update_async_services_seen_for_project

        other_async = ProcessingService.objects.create(name="Other Async", endpoint_url=None)
        other_async.projects.add(self.project)
        sync_service = ProcessingService.objects.create(
            name="Sync Service", endpoint_url="http://nonexistent-host:9999"
        )
        sync_service.projects.add(self.project)
        sync_last_seen_before = ProcessingService.objects.get(pk=sync_service.pk).last_seen

        before = datetime.datetime.now() - datetime.timedelta(seconds=1)
        update_async_services_seen_for_project(self.project.pk)

        self.service.refresh_from_db()
        other_async.refresh_from_db()
        sync_service.refresh_from_db()

        self.assertTrue(self.service.last_seen_live)
        self.assertIsNotNone(self.service.last_seen)
        self.assertGreaterEqual(self.service.last_seen, before)
        self.assertTrue(other_async.last_seen_live)
        # Sync services (with endpoint URL) are not touched by this task — last_seen
        # may be set by the creation-time get_status() ping, but should be unchanged
        # after the task runs.
        self.assertEqual(sync_service.last_seen, sync_last_seen_before)


class TestJobDeletePermission(APITestCase):
    """
    Job records are kept in the DB for audit/traceability. Only superusers may
    delete jobs via the API. Project-scoped roles (MLDataManager, ProjectManager)
    must not have ``delete_job`` regardless of role-permission inheritance, and
    the destroy endpoint must reject their requests.
    """

    def setUp(self):
        from ami.users.roles import MLDataManager, ProjectManager, create_roles_for_project

        self.project = Project.objects.create(name="Job Delete Permission Test Project")
        create_roles_for_project(self.project)

        self.job = Job.objects.create(
            job_type_key=SourceImageCollectionPopulateJob.key,
            project=self.project,
            name="Job slated for delete attempts",
            delay=0,
        )

        self.superuser = User.objects.create_user(
            email="super-jobdel@insectai.org",
            is_staff=True,
            is_active=True,
            is_superuser=True,
        )
        self.ml_manager = User.objects.create_user(
            email="mlmanager-jobdel@insectai.org",
            is_active=True,
        )
        MLDataManager.assign_user(self.ml_manager, self.project)

        self.project_manager = User.objects.create_user(
            email="pm-jobdel@insectai.org",
            is_active=True,
        )
        ProjectManager.assign_user(self.project_manager, self.project)

        self.delete_url = reverse_with_params(
            "api:job-detail",
            args=[self.job.pk],
            params={"project_id": self.project.pk},
        )

    def test_ml_data_manager_role_does_not_have_delete_job(self):
        from ami.users.roles import MLDataManager

        self.assertNotIn("delete_job", MLDataManager.permissions)

    def test_project_manager_role_does_not_have_delete_job(self):
        from ami.users.roles import ProjectManager

        self.assertNotIn("delete_job", ProjectManager.permissions)

    def test_ml_data_manager_cannot_delete_job(self):
        self.client.force_authenticate(user=self.ml_manager)
        resp = self.client.delete(self.delete_url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Job.objects.filter(pk=self.job.pk).exists())

    def test_project_manager_cannot_delete_job(self):
        self.client.force_authenticate(user=self.project_manager)
        resp = self.client.delete(self.delete_url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Job.objects.filter(pk=self.job.pk).exists())

    def test_superuser_can_delete_job(self):
        self.client.force_authenticate(user=self.superuser)
        resp = self.client.delete(self.delete_url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Job.objects.filter(pk=self.job.pk).exists())
