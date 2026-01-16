# from rich import print
import logging
from typing import Any

from django.test import TestCase
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase

from ami.base.serializers import reverse_with_params
from ami.jobs.models import Job, JobProgress, JobState, MLJob, SourceImageCollectionPopulateJob
from ami.main.models import Project, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.users.models import User

logger = logging.getLogger(__name__)


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
        jobs_list_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk, "ids_only": True})
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

        self.client.force_authenticate(user=self.user)
        tasks_url = reverse_with_params(
            "api:job-tasks", args=[job.pk], params={"project_id": self.project.pk, "batch": value}
        )
        resp = self.client.get(tasks_url)
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
        # Use the existing job which doesn't have a pipeline
        job_data = self._create_job("Job without pipeline", start_now=False)

        self.client.force_authenticate(user=self.user)
        tasks_url = reverse_with_params(
            "api:job-tasks", args=[job_data["id"]], params={"project_id": self.project.pk, "batch": 1}
        )
        resp = self.client.get(tasks_url)

        self.assertEqual(resp.status_code, 400)
        self.assertIn("pipeline", resp.json()[0].lower())

    def test_result_endpoint_stub(self):
        """Test the result endpoint accepts results (stubbed implementation)."""
        pipeline = self._create_pipeline()
        job = self._create_ml_job("Job for results test", pipeline)

        self.client.force_authenticate(user=self.user)
        result_url = reverse_with_params(
            "api:job-result", args=[job.pk], params={"project_id": self.project.pk, "batch": 1}
        )

        result_data = [
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

        resp = self.client.post(result_url, result_data, format="json")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "received")
        self.assertEqual(data["job_id"], job.pk)
        self.assertEqual(data["results_received"], 1)
        self.assertIn("message", data)

    def test_result_endpoint_validation(self):
        """Test the result endpoint validates request data."""
        pipeline = self._create_pipeline()
        job = self._create_ml_job("Job for validation test", pipeline)

        self.client.force_authenticate(user=self.user)
        result_url = reverse_with_params("api:job-result", args=[job.pk], params={"project_id": self.project.pk})

        # Test with missing reply_subject
        invalid_data = [{"result": {"pipeline": "test"}}]
        resp = self.client.post(result_url, invalid_data, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("reply_subject", resp.json()[0].lower())

        # Test with missing result
        invalid_data = [{"reply_subject": "test.reply"}]
        resp = self.client.post(result_url, invalid_data, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("result", resp.json()[0].lower())
