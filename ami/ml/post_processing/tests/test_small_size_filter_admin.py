"""Admin-action tests for the migrated Small Size Filter trigger.

Covers the intermediate confirmation page, the per-collection Job creation,
the schema-validated config payload, and form-error re-render.

Fixtures are intentionally minimal: bare Project/Collection/Occurrence rows,
created once per class via ``setUpTestData``. The admin flow only reads FKs —
it never touches captures, taxa, or events — so the full ``setup_test_project``
fixture (storage source, deployment, processing service per call) is wasted
cost here and was what made this module the slowest part of the suite.
"""
from django.contrib import admin as django_admin
from django.test import Client, TestCase
from django.urls import reverse

from ami.jobs.models import Job
from ami.main.models import Occurrence, Project, SourceImageCollection
from ami.users.models import User


class _SmallSizeFilterAdminCase(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_superuser(
            email=f"ssfadmin+{cls.__name__}@example.com",
            password="x",
        )
        cls.project = Project.objects.create(name=f"SSF admin test ({cls.__name__})")
        cls.collection = SourceImageCollection.objects.create(
            project=cls.project,
            name="SSF admin test collection",
        )

    def setUp(self) -> None:
        self.client = Client()
        self.client.force_login(self.superuser)

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
        # Labels derive from SmallSizeFilterTask.name ("Small size filter").
        self.assertIn(b"Run Small size filter", response.content)
        # The form's field is named size_threshold; the rendered <input> uses that name.
        self.assertIn(b'name="size_threshold"', response.content)
        # No Job created on the GET-equivalent step.
        self.assertEqual(
            Job.objects.filter(project=self.project, job_type_key="post_processing").count(),
            0,
        )

    def test_select_across_is_refused_without_creating_jobs(self):
        # "Select all across pages" would serialize the whole table into hidden
        # inputs; the action refuses it instead of rendering an unbounded form.
        response = self._post({"confirm": "yes", "size_threshold": "0.001", "select_across": "1"})
        self.assertEqual(response.status_code, 302)
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


class TestSmallSizeFilterOccurrenceScope(TestCase):
    """The per-occurrence trigger on OccurrenceAdmin uses the same factory with an
    ``occurrence_id`` scope — the fast spot/dev path for iterating on a filter."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_superuser(email="ssfocc@example.com", password="x")
        cls.project = Project.objects.create(name="SSF occurrence-scope test")
        cls.occurrence = Occurrence.objects.create(project=cls.project)

    def setUp(self) -> None:
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_valid_post_creates_one_job_scoped_to_the_occurrence(self):
        url = reverse("admin:main_occurrence_changelist")
        response = self.client.post(
            url,
            data={
                "action": "run_small_size_filter",
                django_admin.helpers.ACTION_CHECKBOX_NAME: [str(self.occurrence.pk)],
                "confirm": "yes",
                "size_threshold": "0.001",
            },
        )
        self.assertEqual(response.status_code, 302)

        job = Job.objects.get(project=self.project, job_type_key="post_processing")
        self.assertEqual(job.params["task"], "small_size_filter")
        self.assertEqual(job.params["config"]["occurrence_id"], self.occurrence.pk)
        # Collection scope stays absent so the schema's exactly-one-scope rule holds.
        self.assertIsNone(job.params["config"].get("source_image_collection_id"))


class TestSmallSizeFilterMultiCollection(_SmallSizeFilterAdminCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        # Second collection in a different project.
        cls.other_project = Project.objects.create(name="SSF admin test (other project)")
        cls.other_collection = SourceImageCollection.objects.create(
            project=cls.other_project,
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
