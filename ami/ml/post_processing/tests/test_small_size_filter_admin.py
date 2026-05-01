"""Admin-action tests for the migrated Small Size Filter trigger.

Covers the intermediate confirmation page, the per-collection Job creation,
the schema-validated config payload, and form-error re-render.
"""
from django.contrib import admin as django_admin
from django.test import Client, TestCase
from django.urls import reverse

from ami.jobs.models import Job
from ami.main.models import SourceImageCollection
from ami.tests.fixtures.main import setup_test_project
from ami.users.models import User


class _SmallSizeFilterAdminCase(TestCase):
    def setUp(self) -> None:
        self.superuser = User.objects.create_superuser(
            email="ssfadmin@example.com",
            password="x",
        )
        self.client = Client()
        self.client.force_login(self.superuser)

        self.project, self.deployment = setup_test_project(reuse=False)
        self.collection = SourceImageCollection.objects.create(
            project=self.project,
            name="SSF admin test collection",
        )

    def _post(self, data: dict, pks: list[int] | None = None):
        url = reverse("admin:main_sourceimagecollection_changelist")
        selected = [str(pk) for pk in (pks or [self.collection.pk])]
        payload = {
            "action": "run_small_size_filter",
            django_admin.helpers.ACTION_CHECKBOX_NAME: selected,
            **data,
        }
        return self.client.post(url, data=payload)


class TestSmallSizeFilterIntermediatePage(_SmallSizeFilterAdminCase):
    def test_renders_intermediate_page_without_confirm(self):
        response = self._post({})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Run Small Size Filter", response.content)
        # The form's field is named size_threshold; the rendered <input> uses that name.
        self.assertIn(b'name="size_threshold"', response.content)
        # No Job created on the GET-equivalent step.
        self.assertEqual(
            Job.objects.filter(project=self.project, job_type_key="post_processing").count(),
            0,
        )

    def test_invalid_threshold_rerenders_form_with_error(self):
        response = self._post({"confirm": "yes", "size_threshold": "2.0"})
        self.assertEqual(response.status_code, 200)
        # No Job created when form fails.
        self.assertEqual(
            Job.objects.filter(project=self.project, job_type_key="post_processing").count(),
            0,
        )
        # Error class present in rendered template.
        self.assertIn(b"errornote", response.content)


class TestSmallSizeFilterCreatesJob(_SmallSizeFilterAdminCase):
    def test_valid_post_creates_one_job_with_threshold_in_config(self):
        response = self._post({"confirm": "yes", "size_threshold": "0.001"})
        self.assertEqual(response.status_code, 302)

        job = Job.objects.get(
            project=self.project,
            job_type_key="post_processing",
        )
        self.assertEqual(job.params["task"], "small_size_filter")
        self.assertEqual(job.params["config"]["size_threshold"], 0.001)
        self.assertEqual(job.params["config"]["source_image_collection_id"], self.collection.pk)

    def test_default_threshold_applies_when_form_uses_initial(self):
        # Submitting the initial value (rendered into the form) creates a job with default threshold.
        response = self._post({"confirm": "yes", "size_threshold": "0.0008"})
        self.assertEqual(response.status_code, 302)

        job = Job.objects.get(
            project=self.project,
            job_type_key="post_processing",
        )
        self.assertEqual(job.params["config"]["size_threshold"], 0.0008)


class TestSmallSizeFilterMultiCollection(_SmallSizeFilterAdminCase):
    def setUp(self) -> None:
        super().setUp()
        # Second collection in a different project.
        self.other_project, _ = setup_test_project(reuse=False)
        self.other_collection = SourceImageCollection.objects.create(
            project=self.other_project,
            name="Other collection",
        )

    def test_multi_collection_creates_one_job_per_collection_with_correct_project_fk(self):
        response = self._post(
            {"confirm": "yes", "size_threshold": "0.001"},
            pks=[self.collection.pk, self.other_collection.pk],
        )
        self.assertEqual(response.status_code, 302)

        jobs = Job.objects.filter(job_type_key="post_processing").order_by("project_id")
        self.assertEqual(jobs.count(), 2)

        by_project = {j.project_id: j for j in jobs}
        self.assertEqual(
            by_project[self.project.pk].params["config"]["source_image_collection_id"],
            self.collection.pk,
        )
        self.assertEqual(
            by_project[self.other_project.pk].params["config"]["source_image_collection_id"],
            self.other_collection.pk,
        )
