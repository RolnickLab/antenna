"""Admin-action tests for the Occurrence Tracking trigger.

Covers both entry points. The Events changelist can span projects, so its
selection is partitioned into one Job per project; the capture-set changelist
uses the shared one-Job-per-row path.
"""
from django.contrib import admin as django_admin
from django.test import Client, TestCase
from django.urls import reverse

from ami.jobs.models import Job
from ami.main.models import SourceImageCollection
from ami.tests.fixtures.main import create_captures, setup_test_project
from ami.users.models import User


class _TrackingAdminCase(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_superuser(
            email=f"trackadmin+{cls.__name__}@example.com",
            password="x",
        )
        cls.project, cls.deployment = setup_test_project(reuse=False)
        create_captures(deployment=cls.deployment, num_nights=1, images_per_night=2, interval_minutes=1)
        event = cls.project.events.first()
        assert event is not None
        cls.event = event

    def setUp(self) -> None:
        self.client = Client()
        self.client.force_login(self.superuser)

    @staticmethod
    def _knobs(**overrides) -> dict:
        """Form payload for a confirmed submit. Unchecked booleans are absent, as in HTML."""
        return {
            "confirm": "yes",
            "cost_threshold": "0.2",
            "skip_if_human_identifications": "on",
            "require_features": "on",
            "require_fresh_event": "on",
            "feature_extraction_algorithm_id": "",
            **overrides,
        }


class TestEventAdminTrackingAction(_TrackingAdminCase):
    def _post(self, data: dict, pks: list[int] | None = None):
        url = reverse("admin:main_event_changelist")
        selected = [str(pk) for pk in (pks or [self.event.pk])]
        return self.client.post(
            url,
            data={
                "action": "run_tracking",
                django_admin.helpers.ACTION_CHECKBOX_NAME: selected,
                **data,
            },
        )

    def test_renders_intermediate_page_without_confirm(self):
        response = self._post({})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Run Occurrence Tracking", response.content)
        self.assertIn(b'name="cost_threshold"', response.content)
        self.assertEqual(Job.objects.filter(job_type_key="post_processing").count(), 0)

    def test_creates_one_job_per_project_carrying_its_own_events(self):
        other_project, other_deployment = setup_test_project(reuse=False)
        create_captures(deployment=other_deployment, num_nights=1, images_per_night=2, interval_minutes=1)
        other_event = other_project.events.first()
        assert other_event is not None

        response = self._post(
            self._knobs(cost_threshold="0.35", require_fresh_event=""),
            pks=[self.event.pk, other_event.pk],
        )
        self.assertEqual(response.status_code, 302)

        jobs = Job.objects.filter(job_type_key="post_processing")
        self.assertEqual(jobs.count(), 2)
        by_project = {job.project_id: job for job in jobs}
        self.assertEqual(set(by_project), {self.project.pk, other_project.pk})

        for job in jobs:
            config = job.params["config"]
            self.assertEqual(config["cost_threshold"], 0.35)
            self.assertTrue(config["skip_if_human_identifications"])
            self.assertFalse(config["require_fresh_event"])
            self.assertIsNone(config["feature_extraction_algorithm_id"])

        self.assertEqual(by_project[self.project.pk].params["config"]["event_ids"], [self.event.pk])
        self.assertEqual(by_project[other_project.pk].params["config"]["event_ids"], [other_event.pk])


class TestCollectionAdminTrackingAction(_TrackingAdminCase):
    def setUp(self) -> None:
        super().setUp()
        self.collection = SourceImageCollection.objects.create(
            project=self.project, name="Tracking admin test collection"
        )
        self.collection.images.set(self.event.captures.all())

    def test_creates_job_scoped_to_the_capture_set(self):
        response = self.client.post(
            reverse("admin:main_sourceimagecollection_changelist"),
            data={
                "action": "run_tracking",
                django_admin.helpers.ACTION_CHECKBOX_NAME: [str(self.collection.pk)],
                **self._knobs(require_features=""),
            },
        )
        self.assertEqual(response.status_code, 302)

        job = Job.objects.get(job_type_key="post_processing")
        self.assertEqual(job.project_id, self.project.pk)
        self.assertEqual(job.params["config"]["source_image_collection_id"], self.collection.pk)
        self.assertEqual(job.params["config"]["event_ids"], [])
        self.assertFalse(job.params["config"]["require_features"])
