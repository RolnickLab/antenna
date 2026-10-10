"""Admin-action tests for the Occurrence tracking trigger.

The Sessions (events) changelist can span projects, so its selection becomes one Job per project; the
capture-set changelist uses the shared one-Job-per-row path. The form is generated from ``TrackingConfig``.
"""
from django.contrib import admin as django_admin
from django.test import Client, TestCase
from django.urls import reverse

from ami.base.model_references import ModelRef
from ami.jobs.job_config import job_config_fields
from ami.jobs.models import Job
from ami.main.models import Project, SourceImageCollection
from ami.ml.post_processing.tracking import TrackingConfig
from ami.tests.fixtures.main import create_captures, setup_test_project
from ami.users.models import User

COST_FIELDS = (
    "cost_threshold",
    "iou_weight",
    "size_weight",
    "distance_weight",
    "min_iou",
    "min_size_ratio",
    "max_distance",
    "max_capture_interval_seconds",
)


class _TrackingAdminCase(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_superuser(email=f"trackadmin+{cls.__name__}@example.com", password="x")
        cls.project, cls.deployment = setup_test_project(reuse=False)
        create_captures(deployment=cls.deployment, num_nights=1, images_per_night=2, interval_minutes=1)
        cls.event = cls.project.events.first()
        assert cls.event is not None

    def setUp(self) -> None:
        self.client = Client()
        self.client.force_login(self.superuser)

    @staticmethod
    def _knobs(**overrides) -> dict:
        """Form payload for a confirmed submit. Unchecked booleans are absent, as in HTML."""
        return {
            "confirm": "yes",
            "cost_threshold": "1.0",
            "iou_weight": "1.0",
            "size_weight": "1.0",
            "distance_weight": "1.0",
            "skip_if_human_identifications": "on",
            "require_fresh_event": "on",
            **overrides,
        }


class TestEventAdminTrackingAction(_TrackingAdminCase):
    def _post(self, data: dict, pks: list[int] | None = None):
        selected = [str(pk) for pk in (pks or [self.event.pk])]
        return self.client.post(
            reverse("admin:main_event_changelist"),
            data={"action": "run_tracking", django_admin.helpers.ACTION_CHECKBOX_NAME: selected, **data},
        )

    def test_renders_every_tunable_with_its_help_text_and_creates_no_job(self):
        response = self._post({})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Run Occurrence tracking")
        for name in COST_FIELDS:
            self.assertContains(response, f'name="{name}"')
            self.assertContains(response, TrackingConfig.__fields__[name].field_info.title)
        self.assertContains(response, "about 20 seconds apart")
        self.assertNotContains(response, 'name="event_ids"')
        self.assertEqual(Job.objects.filter(job_type_key="post_processing").count(), 0)

    def test_creates_one_job_per_project_carrying_its_own_events_and_non_default_values(self):
        other_project, other_deployment = setup_test_project(reuse=False)
        create_captures(deployment=other_deployment, num_nights=1, images_per_night=2, interval_minutes=1)
        other_event = other_project.events.first()
        assert other_event is not None

        response = self._post(
            self._knobs(
                cost_threshold="0.35", min_iou="0.25", max_capture_interval_seconds="45", require_fresh_event=""
            ),
            pks=[self.event.pk, other_event.pk],
        )
        self.assertEqual(response.status_code, 302)

        jobs = {job.project_id: job for job in Job.objects.filter(job_type_key="post_processing")}
        self.assertEqual(set(jobs), {self.project.pk, other_project.pk})
        for job in jobs.values():
            config = job.params["config"]
            self.assertEqual(job.params["task"], "tracking")
            self.assertEqual(config["cost_threshold"], 0.35)
            self.assertEqual(config["min_iou"], 0.25)
            self.assertEqual(config["max_capture_interval_seconds"], 45)
            self.assertIsNone(config["max_distance"])
            self.assertTrue(config["skip_if_human_identifications"])
            self.assertFalse(config["require_fresh_event"])
        self.assertEqual(jobs[self.project.pk].params["config"]["event_ids"], [self.event.pk])
        self.assertEqual(jobs[other_project.pk].params["config"]["event_ids"], [other_event.pk])

    def test_the_jobs_sessions_are_named_as_records(self):
        """The job's config names its sessions as references, so the history can link them."""
        self._post(self._knobs())
        job = Job.objects.get(job_type_key="post_processing")

        sessions = next(field for field in job_config_fields([job])[job.pk] if field.key == "event_ids")

        self.assertEqual(sessions.label, "Sessions")
        self.assertEqual(sessions.refs, [ModelRef("session", self.event.pk, self.event.name())])

    def test_an_out_of_range_value_is_shown_on_the_form_and_creates_no_job(self):
        response = self._post(self._knobs(min_iou="1.5"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors.get("min_iou"))
        self.assertEqual(Job.objects.filter(job_type_key="post_processing").count(), 0)

    def test_a_zero_interval_is_refused_by_the_schema_and_shown_on_the_field(self):
        response = self._post(self._knobs(max_capture_interval_seconds="0"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors.get("max_capture_interval_seconds"))
        self.assertEqual(Job.objects.filter(job_type_key="post_processing").count(), 0)

    def test_sessions_without_a_project_are_refused(self):
        orphan = self.event
        type(orphan).objects.filter(pk=orphan.pk).update(project=None)
        response = self._post(self._knobs())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "have no project")
        self.assertEqual(Job.objects.filter(job_type_key="post_processing").count(), 0)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())


class TestCollectionAdminTrackingAction(_TrackingAdminCase):
    def test_creates_a_job_scoped_to_the_capture_set(self):
        collection = SourceImageCollection.objects.create(project=self.project, name="Tracking admin test set")
        collection.images.set(self.event.captures.all())

        response = self.client.post(
            reverse("admin:main_sourceimagecollection_changelist"),
            data={
                "action": "run_tracking",
                django_admin.helpers.ACTION_CHECKBOX_NAME: [str(collection.pk)],
                **self._knobs(distance_weight="2.5", max_distance="0.1"),
            },
        )
        self.assertEqual(response.status_code, 302)

        job = Job.objects.get(job_type_key="post_processing")
        self.assertEqual(job.project_id, self.project.pk)
        config = job.params["config"]
        self.assertEqual(config["source_image_collection_id"], collection.pk)
        self.assertEqual(config["event_ids"], [])
        self.assertEqual(config["distance_weight"], 2.5)
        self.assertEqual(config["max_distance"], 0.1)
