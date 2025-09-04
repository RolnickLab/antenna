# from rich import print
import logging
import time

from django.test import TestCase
from guardian.shortcuts import assign_perm
from rest_framework.test import APIRequestFactory, APITestCase

from ami.base.serializers import reverse_with_params
from ami.jobs.models import (
    Job,
    JobProgress,
    JobState,
    MLJob,
    MLSubtaskNames,
    MLSubtaskState,
    SourceImageCollectionPopulateJob,
)
from ami.main.models import Project, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.tests.fixtures.main import create_captures_from_files, create_processing_service, setup_test_project
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
        self.assertEqual(resp.status_code, 401)

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

        assign_perm(Project.Permissions.RUN_JOB, self.user, self.project)

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
        self.assertEqual(resp.status_code, 401)

    def test_cancel_job(self):
        # This cannot be tested until we have a way to cancel jobs
        # and a way to run async tasks in tests.
        pass


class TestMLJobBatchProcessing(TestCase):
    def setUp(self):
        self.project, self.deployment = setup_test_project()
        self.captures = create_captures_from_files(self.deployment, skip_existing=False)
        self.source_image_collection = SourceImageCollection.objects.get(
            name="Test Source Image Collection",
            project=self.project,
        )
        self.processing_service_instance = create_processing_service(self.project)
        self.processing_service = self.processing_service_instance
        assert self.processing_service_instance.pipelines.exists()
        self.pipeline = self.processing_service_instance.pipelines.all().get(slug="constant")

    def _check_correct_job_progress(
        self, job: Job, expected_num_process_subtasks: int, expected_num_results_subtasks: int
    ):
        """Helper function to check that the job progress is correct."""
        # Check that the job stages are as expected
        self.assertEqual(job.progress.stages[0].key, "delay")
        self.assertEqual(job.progress.stages[1].key, "collect")
        self.assertEqual(job.progress.stages[2].key, "process")
        self.assertEqual(job.progress.stages[3].key, "results")

        # Get all MLTaskRecords which are created
        completed_process_subtasks = job.ml_task_records.filter(
            task_name=MLSubtaskNames.process_pipeline_request.value,
            status__in=[MLSubtaskState.SUCCESS.value, MLSubtaskState.FAIL.value],
        )
        completed_results_subtasks = job.ml_task_records.filter(
            task_name=MLSubtaskNames.save_results.value,
            status__in=[MLSubtaskState.SUCCESS.value, MLSubtaskState.FAIL.value],
        )

        if (
            completed_process_subtasks.count() < expected_num_process_subtasks
            or completed_results_subtasks.count() < expected_num_results_subtasks
        ):
            # If there are any in-progress subtasks, the job should be IN_PROGRESS
            self.assertEqual(job.status, JobState.STARTED.value)
            self.assertEqual(job.progress.summary.status, JobState.STARTED)
            self.assertGreater(job.progress.summary.progress, 0)
            self.assertLess(job.progress.summary.progress, 1)

        if completed_process_subtasks.count() == expected_num_process_subtasks:
            # If there are no in-progress process subtasks, the process stage should be SUCCESS
            self.assertEqual(job.progress.stages[2].status, JobState.SUCCESS)
            self.assertEqual(job.progress.stages[2].progress, 1)
        else:
            # If there are in-progress process subtasks, the process stage should be IN_PROGRESS
            self.assertEqual(job.progress.stages[2].status, JobState.STARTED)
            self.assertGreater(job.progress.stages[2].progress, 0)
            self.assertLess(job.progress.stages[2].progress, 1)

        if completed_results_subtasks.count() == expected_num_results_subtasks:
            # If there are no in-progress results subtasks, the results stage should be SUCCESS
            self.assertEqual(job.progress.stages[3].status, JobState.SUCCESS)
            self.assertEqual(job.progress.stages[3].progress, 1)
        else:
            # If there are in-progress results subtasks, the results stage should be IN_PROGRESS
            self.assertEqual(job.progress.stages[3].status, JobState.STARTED)
            # self.assertGreater(job.progress.stages[3].progress, 0) # the results stage could be at 0 progress
            self.assertLess(job.progress.stages[3].progress, 1)

    def test_run_ml_job(self):
        """Test running a batch processing job end-to-end."""
        logger.info(
            f"Starting test_batch_processing_job using collection "
            f"{self.source_image_collection} which contains "
            f"{self.source_image_collection.images.count()} images"
        )
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test batch processing",
            delay=1,
            pipeline=self.pipeline,
            source_image_collection=self.source_image_collection,
        )
        self.assertEqual(job.progress.stages[0].key, "delay")
        self.assertEqual(job.progress.stages[0].progress, 0)
        self.assertEqual(job.progress.stages[0].status, JobState.CREATED)
        self.assertEqual(job.progress.stages[1].key, "collect")
        self.assertEqual(job.progress.stages[1].progress, 0)
        self.assertEqual(job.progress.stages[1].status, JobState.CREATED)
        self.assertEqual(job.progress.stages[2].key, "process")
        self.assertEqual(job.progress.stages[2].progress, 0)
        self.assertEqual(job.progress.stages[2].status, JobState.CREATED)
        self.assertEqual(job.progress.stages[3].key, "results")
        self.assertEqual(job.progress.stages[3].progress, 0)
        self.assertEqual(job.progress.stages[3].status, JobState.CREATED)

        self.assertEqual(job.status, JobState.CREATED.value)
        self.assertEqual(job.progress.summary.progress, 0)
        self.assertEqual(job.progress.summary.status, JobState.CREATED)

        job.run()

        start_time = time.time()
        timeout = 600  # seconds
        elapsed_time = 0
        while elapsed_time < timeout:
            job.check_inprogress_subtasks()
            if job.status == JobState.SUCCESS.value or job.status == JobState.FAILURE.value:
                break
            elapsed_time = time.time() - start_time
            logger.info(f"Waiting for job to complete... elapsed time: {elapsed_time:.2f} seconds")
            self._check_correct_job_progress(job, expected_num_process_subtasks=6, expected_num_results_subtasks=6)
            time.sleep(3)

        # Check all subtasks were successful
        ml_subtask_records = job.ml_task_records.all()
        self.assertEqual(
            ml_subtask_records.count(), self.source_image_collection.images.count() * 2
        )  # 2 subtasks per image (process and results)
        self.assertTrue(all(subtask.status == MLSubtaskState.SUCCESS.value for subtask in ml_subtask_records))

        # Check all the progress stages are marked as SUCCESS
        self.assertEqual(job.status, JobState.SUCCESS.value)
        self.assertEqual(job.progress.stages[0].key, "delay")
        self.assertEqual(job.progress.stages[0].progress, 1)
        self.assertEqual(job.progress.stages[0].status, JobState.SUCCESS)
        self.assertEqual(job.progress.stages[1].key, "collect")
        self.assertEqual(job.progress.stages[1].progress, 1)
        self.assertEqual(job.progress.stages[1].status, JobState.SUCCESS)
        self.assertEqual(job.progress.stages[2].key, "process")
        self.assertEqual(job.progress.stages[2].progress, 1)
        self.assertEqual(job.progress.stages[2].status, JobState.SUCCESS)
        self.assertEqual(job.progress.stages[3].key, "results")
        self.assertEqual(job.progress.stages[3].progress, 1)
        self.assertEqual(job.progress.stages[3].status, JobState.SUCCESS)

        self.assertEqual(job.status, JobState.SUCCESS.value)
        self.assertEqual(job.progress.summary.progress, 1)
        self.assertEqual(job.progress.summary.status, JobState.SUCCESS)
        job.save()

        # Check that the detections were created correctly (i.e. 1 per image)
        # Get the source image processed by the job
        for image in self.source_image_collection.images.all():
            jobs = image.jobs.filter(id=job.pk)
            if job in jobs:
                logger.info(f"Image {image.id} was processed by job {job.pk}")
                detections = image.detections.all()
                # log the detections for debugging
                logger.info(f"Image {image.id} has detections: {detections}")
                num_detections = image.get_detections_count()
                assert num_detections == 1, f"Image {image.id} has {num_detections} detections instead of 1"
            else:
                logger.error(f"Image {image.id} was NOT processed by job {job.pk}")
