"""Admin-action tests for the Occurrence Tracking trigger.

Covers both entry-points (EventAdmin + SourceImageCollectionAdmin), exercising
the intermediate confirmation page, the per-project Job partition, and the
config-passthrough from form to ``Job.params['config']``.
"""
from django.contrib import admin as django_admin
from django.test import Client, TestCase
from django.urls import reverse

from ami.jobs.models import Job
from ami.main.models import SourceImageCollection
from ami.tests.fixtures.main import create_captures, setup_test_project
from ami.users.models import User


class _AdminTrackingCase(TestCase):
    def setUp(self) -> None:
        self.superuser = User.objects.create_superuser(
            email="trackadmin@example.com",
            password="x",
        )
        self.client = Client()
        self.client.force_login(self.superuser)

        self.project, self.deployment = setup_test_project(reuse=False)
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=2, interval_minutes=1)
        self.event = self.project.events.first()
        assert self.event is not None


class TestEventAdminTrackingAction(_AdminTrackingCase):
    def _post_action(self, data):
        url = reverse("admin:main_event_changelist")
        payload = {
            "action": "run_tracking_on_events",
            django_admin.helpers.ACTION_CHECKBOX_NAME: [str(self.event.pk)],
            **data,
        }
        return self.client.post(url, data=payload)

    def test_renders_intermediate_page_without_confirm(self):
        response = self._post_action({})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Run Occurrence Tracking", response.content)
        self.assertIn(b"Tracking parameters", response.content)
        # No Job created on the GET-equivalent step.
        self.assertEqual(Job.objects.filter(project=self.project, job_type_key="post_processing").count(), 0)

    def test_creates_job_per_project_and_passes_config_through(self):
        # Build a second event in a different project to exercise per-project partitioning.
        other_project, other_deployment = setup_test_project(reuse=False)
        create_captures(deployment=other_deployment, num_nights=1, images_per_night=2, interval_minutes=1)
        other_event = other_project.events.first()
        assert other_event is not None

        url = reverse("admin:main_event_changelist")
        response = self.client.post(
            url,
            data={
                "action": "run_tracking_on_events",
                django_admin.helpers.ACTION_CHECKBOX_NAME: [str(self.event.pk), str(other_event.pk)],
                "confirm": "yes",
                "cost_threshold": "0.35",
                "skip_if_human_identifications": "on",
                # require_fresh_event intentionally omitted = unchecked.
                "feature_extraction_algorithm_id": "",
            },
        )
        self.assertEqual(response.status_code, 302)

        jobs = Job.objects.filter(job_type_key="post_processing").order_by("project_id")
        self.assertEqual(jobs.count(), 2)
        by_project = {j.project_id: j for j in jobs}
        self.assertIn(self.project.pk, by_project)
        self.assertIn(other_project.pk, by_project)

        for job in jobs:
            cfg = job.params["config"]
            self.assertEqual(cfg["cost_threshold"], 0.35)
            self.assertTrue(cfg["skip_if_human_identifications"])
            self.assertFalse(cfg["require_fresh_event"])
            self.assertNotIn("feature_extraction_algorithm_id", cfg)
            # Each job carries only its own project's events.
            self.assertEqual(len(cfg["event_ids"]), 1)

        self.assertEqual(by_project[self.project.pk].params["config"]["event_ids"], [self.event.pk])
        self.assertEqual(by_project[other_project.pk].params["config"]["event_ids"], [other_event.pk])


class TestCollectionAdminTrackingAction(_AdminTrackingCase):
    def setUp(self) -> None:
        super().setUp()
        self.collection = SourceImageCollection.objects.create(
            project=self.project, name="Tracking admin test collection"
        )
        self.collection.images.set(self.event.captures.all())

    def test_creates_job_with_event_ids_from_collection(self):
        url = reverse("admin:main_sourceimagecollection_changelist")
        response = self.client.post(
            url,
            data={
                "action": "run_tracking",
                django_admin.helpers.ACTION_CHECKBOX_NAME: [str(self.collection.pk)],
                "confirm": "yes",
                "cost_threshold": "0.2",
                "skip_if_human_identifications": "on",
                "require_fresh_event": "on",
                "feature_extraction_algorithm_id": "",
            },
        )
        self.assertEqual(response.status_code, 302)

        job = Job.objects.get(job_type_key="post_processing", source_image_collection=self.collection)
        self.assertEqual(job.project_id, self.project.pk)
        self.assertEqual(job.params["config"]["event_ids"], [self.event.pk])
