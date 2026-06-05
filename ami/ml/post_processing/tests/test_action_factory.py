"""Tests for the shared post-processing admin-action factory.

Covers the generic glue in ``ami/ml/post_processing/admin/actions.py``: the
action's registered name, the default one-Job-per-row builder (task key, scope
injection, project FK), schema-error mapping back onto form fields, and the
``build_jobs`` override hook used by tasks with a non-default row→Job mapping.
"""
import pytest
from django.contrib import admin as django_admin
from django.test import RequestFactory, TestCase

from ami.jobs.models import Job
from ami.main.models import SourceImageCollection
from ami.ml.post_processing.admin.actions import (
    ConfigValidationErrors,
    default_build_jobs,
    make_post_processing_action,
)
from ami.ml.post_processing.admin.small_size_filter_form import SmallSizeFilterActionForm
from ami.ml.post_processing.small_size_filter import SmallSizeFilterTask
from ami.tests.fixtures.main import setup_test_project


def _ssf_kwargs(queryset, config):
    """Common keyword arguments for invoking the small-size-filter job builder."""
    return dict(
        model_admin=None,
        request=None,
        config=config,
        queryset=queryset,
        task_cls=SmallSizeFilterTask,
        form_field_names={"size_threshold"},
        scope_resolver=lambda c: {"source_image_collection_id": c.pk},
        project_resolver=lambda c: c.project,
        name_resolver=lambda task_cls, c: f"SSF {c.pk}",
    )


class TestActionRegistration(TestCase):
    def test_action_name_is_run_plus_task_key(self):
        action = make_post_processing_action(
            SmallSizeFilterTask,
            SmallSizeFilterActionForm,
            scope_resolver=lambda c: {"source_image_collection_id": c.pk},
        )
        self.assertEqual(action.__name__, "run_small_size_filter")

    def test_default_description_derives_from_task_name(self):
        action = make_post_processing_action(
            SmallSizeFilterTask,
            SmallSizeFilterActionForm,
            scope_resolver=lambda c: {"source_image_collection_id": c.pk},
        )
        # @admin.action stores the dropdown label on the function.
        self.assertEqual(action.short_description, "Run Small size filter post-processing task (async)")

    def test_requires_scope_resolver_or_build_jobs(self):
        with pytest.raises(ValueError, match="scope_resolver"):
            make_post_processing_action(SmallSizeFilterTask, SmallSizeFilterActionForm)


class TestDefaultBuildJobs(TestCase):
    def setUp(self) -> None:
        self.project, _ = setup_test_project(reuse=False)
        self.collection = SourceImageCollection.objects.create(project=self.project, name="c1")

    def test_creates_one_job_per_row_with_task_key_and_scope(self):
        qs = SourceImageCollection.objects.filter(pk=self.collection.pk)
        job_pks = default_build_jobs(**_ssf_kwargs(qs, {"size_threshold": 0.001}))

        self.assertEqual(len(job_pks), 1)
        job = Job.objects.get(pk=job_pks[0])
        self.assertEqual(job.project_id, self.project.pk)
        self.assertEqual(job.job_type_key, "post_processing")
        self.assertEqual(job.params["task"], "small_size_filter")
        self.assertEqual(job.params["config"]["size_threshold"], 0.001)
        self.assertEqual(job.params["config"]["source_image_collection_id"], self.collection.pk)

    def test_out_of_range_config_raises_and_creates_no_jobs(self):
        qs = SourceImageCollection.objects.filter(pk=self.collection.pk)
        with pytest.raises(ConfigValidationErrors) as exc_info:
            default_build_jobs(**_ssf_kwargs(qs, {"size_threshold": 2.0}))

        # The bad field is one the form renders, so it maps to that field (not non-field).
        fields = {field for field, _ in exc_info.value.errors}
        self.assertIn("size_threshold", fields)
        self.assertEqual(Job.objects.filter(job_type_key="post_processing").count(), 0)

    def test_all_or_nothing_when_one_row_is_invalid(self):
        good = SourceImageCollection.objects.create(project=self.project, name="good")
        qs = SourceImageCollection.objects.filter(pk__in=[self.collection.pk, good.pk])
        # size_threshold out of range fails for every row -> nothing created.
        with pytest.raises(ConfigValidationErrors):
            default_build_jobs(**_ssf_kwargs(qs, {"size_threshold": 5.0}))
        self.assertEqual(Job.objects.filter(job_type_key="post_processing").count(), 0)


class _StubAdmin:
    """Minimal ModelAdmin stand-in for invoking an action outside the admin site."""

    model = SourceImageCollection
    admin_site = django_admin.site

    def __init__(self) -> None:
        self.messages: list[tuple[str, object]] = []

    def message_user(self, request, message, level=None, **kwargs) -> None:
        self.messages.append((message, level))


class TestBuildJobsOverrideHook(TestCase):
    def setUp(self) -> None:
        self.project, _ = setup_test_project(reuse=False)
        self.collection = SourceImageCollection.objects.create(project=self.project, name="c1")

    def test_custom_build_jobs_is_used_instead_of_default(self):
        calls = {}

        def custom_build_jobs(**kwargs):
            calls.update(kwargs)
            return [101, 102]

        action = make_post_processing_action(
            SmallSizeFilterTask,
            SmallSizeFilterActionForm,
            build_jobs=custom_build_jobs,
        )
        # build_jobs supplied, so scope_resolver is optional (no ValueError on construction).
        self.assertEqual(action.__name__, "run_small_size_filter")

        # Actually invoke the action through the confirm leg so the custom runner runs.
        request = RequestFactory().post("/", data={"confirm": "yes", "size_threshold": "0.001"})
        admin_stub = _StubAdmin()
        queryset = SourceImageCollection.objects.filter(pk=self.collection.pk)

        result = action(admin_stub, request, queryset)

        # Success leg returns None and reports the pks the custom runner produced.
        self.assertIsNone(result)
        self.assertTrue(calls, "custom build_jobs was never invoked")
        self.assertEqual(calls["task_cls"], SmallSizeFilterTask)
        self.assertEqual(calls["config"], {"size_threshold": 0.001})
        # scope_resolver was not supplied, so it must not be forwarded as None.
        self.assertNotIn("scope_resolver", calls)
        self.assertEqual(len(admin_stub.messages), 1)
        self.assertIn("[101, 102]", admin_stub.messages[0][0])
