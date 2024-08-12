from django.test import TestCase
from rest_framework.test import APIRequestFactory, APITestCase

from ami.base.serializers import reverse_with_params
from ami.jobs.models import Job, JobProgress, JobState
from ami.main.models import Project, SourceImageCollection
from ami.ml.models import Pipeline
from ami.users.models import User

# from rich import print


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
        job = Job.objects.create(project=self.project, name="Test job")
        self.assertIsInstance(job.progress, JobProgress)
        self.assertEqual(job.progress.summary.progress, 0)
        self.assertEqual(job.progress.stages, [])

    def test_create_job_with_delay(self):
        job = Job.objects.create(
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
        self.job = Job.objects.create(
            project=self.project,
            name="Test job",
            delay=0,
            pipeline=Pipeline.objects.create(name="Test pipeline"),
            source_image_collection=SourceImageCollection.objects.create(
                name="Test collection",
                project=self.project,
            ),
        )

        self.user = User.objects.create_user(  # type: ignore
            email="testuser@insectai.org",
            is_staff=True,
        )
        self.factory = APIRequestFactory()

    def test_get_job(self):
        # resp = self.client.get(f"/api/jobs/{self.job.pk}/")
        jobs_retrieve_url = reverse_with_params("api:job-detail", args=[self.job.pk])
        resp = self.client.get(jobs_retrieve_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], self.job.pk)

    def test_get_job_list(self):
        # resp = self.client.get("/api/jobs/")
        jobs_list_url = reverse_with_params("api:job-list")
        resp = self.client.get(jobs_list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    def test_create_job_unauthenticated(self):
        jobs_create_url = reverse_with_params("api:job-list")
        job_data = {
            "project_id": self.project.pk,
            "name": "Test job unauthenticated",
            "delay": 0,
        }
        self.client.force_authenticate(user=None)
        resp = self.client.post(jobs_create_url, job_data)
        self.assertEqual(resp.status_code, 403)

    def test_create_job(self):
        jobs_create_url = reverse_with_params("api:job-list")
        # request = self.factory.post(jobs_create_url, {"project": self.project.pk, "name": "Test job 2"})
        self.client.force_authenticate(user=self.user)
        job_data = {
            "project_id": self.job.project.pk,
            "name": "Test job 2",
            "pipeline_id": self.job.pipeline.pk,  # type: ignore
            "collection_id": self.job.source_image_collection.pk,  # type: ignore
            "delay": 0,
            "start_now": False,
        }
        resp = self.client.post(jobs_create_url, job_data)
        self.client.force_authenticate(user=None)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["project"]["id"], self.project.pk)
        self.assertEqual(data["name"], "Test job 2")
        # self.assertEqual(data["progress"]["status"], "CREATED")
        progress = JobProgress(**data["progress"])

        self.assertEqual(progress.summary.status, JobState.SUCCESS)

    def test_run_job(self):
        jobs_run_url = reverse_with_params("api:job-run", args=[self.job.pk], params={"no_async": True})
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(jobs_run_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], self.job.pk)
        self.assertEqual(data["status"], JobState.SUCCESS.value)
        progress = JobProgress(**data["progress"])
        self.assertEqual(progress.summary.status, JobState.SUCCESS)
        self.assertEqual(progress.summary.progress, 1.0)
        # self.job.refresh_from_db()
        # Assert has a task id now, if async is working in tests
        # self.assertIsNotNone(self.job.task_id)

    def test_run_job_unauthenticated(self):
        jobs_run_url = reverse_with_params("api:job-run", args=[self.job.pk])
        self.client.force_authenticate(user=None)
        resp = self.client.post(jobs_run_url)
        self.assertEqual(resp.status_code, 403)

    def test_cancel_job(self):
        # This cannot be tested until we have a way to cancel jobs
        # and a way to run async tasks in tests.
        pass
