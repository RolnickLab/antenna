"""Tests for the Project model, its manager, and its queryset annotations."""

import datetime

from cachalot.api import cachalot_disabled
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from ami.main.models import Deployment, Device, Event, Occurrence, Site, SourceImage, SourceImageCollection
from ami.main.models_future.projects import Project
from ami.main.models_future.taxonomy import Taxon
from ami.ml.models.project_pipeline_config import ProjectPipelineConfig
from ami.users.models import User


class TestProjectSetup(TestCase):
    def test_project_creation(self):
        project = Project.objects.create(name="New Project with Defaults", create_defaults=True)
        self.assertIsInstance(project, Project)

    def test_default_related_models(self):
        """Test that the default related models are created correctly when a project is created."""
        project = Project.objects.create(name="New Project with Defaults", create_defaults=True)

        # Check that the project has a default deployment
        self.assertGreaterEqual(project.deployments.count(), 1)
        deployment = project.deployments.first()
        self.assertIsInstance(deployment, Deployment)

        # Check that the deployment has a default site
        self.assertGreaterEqual(project.sites.count(), 1)
        site = project.sites.first()
        self.assertIsInstance(site, Site)

        # Check that the deployment has a default device
        self.assertGreaterEqual(project.devices.count(), 1)
        device = project.devices.first()
        self.assertIsInstance(device, Device)

        # Check that the project has a default source image collection
        self.assertGreaterEqual(project.sourceimage_collections.count(), 1)
        collection = project.sourceimage_collections.first()
        self.assertIsInstance(collection, SourceImageCollection)

    # Disable this test for now, as it requires a more complex setup
    def no_test_default_permissions(self):
        pass

    @override_settings(
        DEFAULT_PROCESSING_SERVICE_NAME="Default Processing Service",
        DEFAULT_PROCESSING_SERVICE_ENDPOINT="http://ml_backend:2009/",
    )
    def test_processing_service_if_configured(self):
        """
        Test that the default processing service is created if the environment variables are set.
        """
        from ami.ml.models.processing_service import get_or_create_default_processing_service

        project = Project.objects.create(name="Test Project for Processing Service", create_defaults=False)

        service = get_or_create_default_processing_service(project=project, register_pipelines=False)
        self.assertIsNotNone(service, "Default processing service should be created if environment variables are set.")
        assert service is not None  # For type checking
        self.assertIsNotNone(service.endpoint_url)
        self.assertIsNotNone(service.name)
        self.assertGreaterEqual(project.processing_services.count(), 1)

    @override_settings(
        DEFAULT_PROCESSING_SERVICE_NAME=None,
        DEFAULT_PROCESSING_SERVICE_ENDPOINT=None,
    )
    def test_processing_service_if_not_configured(self):
        """
        Test that the default processing service is not created if the environment variables are not set.
        """
        from ami.ml.models.processing_service import get_or_create_default_processing_service

        project = Project.objects.create(name="Test Project for Processing Service", create_defaults=False)

        service = get_or_create_default_processing_service(project=project)
        self.assertIsNone(
            service, "Default processing service should not be created if environment variables are not set."
        )

    @override_settings(
        DEFAULT_PROCESSING_SERVICE_NAME="Default Processing Service",
        DEFAULT_PROCESSING_SERVICE_ENDPOINT="http://ml_backend:2000/",
        DEFAULT_PIPELINES_ENABLED=[],  # All pipelines DISABLED by default
    )
    def test_processing_service_with_disabled_pipelines(self):
        """
        Test that the default processing service is created with all pipelines disabled
        if DEFAULT_PIPELINES_ENABLED is any empty list.
        """
        project = Project.objects.create(name="Test Project for Processing Service", create_defaults=True)
        processing_service = project.processing_services.first()
        assert processing_service is not None
        # There should be at least two pipelines created by default
        self.assertGreaterEqual(processing_service.pipelines.count(), 2)
        # All pipelines should be disabled by default
        project_pipeline_configs = ProjectPipelineConfig.objects.filter(project=project)
        for config in project_pipeline_configs:
            self.assertFalse(
                config.enabled,
                f"Pipeline {config.pipeline.name} should be disabled for project {project.name}.",
            )

    @override_settings(
        DEFAULT_PROCESSING_SERVICE_NAME="Default Processing Service",
        DEFAULT_PROCESSING_SERVICE_ENDPOINT="http://ml_backend:2000/",
        DEFAULT_PIPELINES_ENABLED=None,  # All pipelines ENABLED by default
    )
    def test_processing_service_with_enabled_pipelines(self):
        """
        Test that the default processing service is created with all pipelines enabled
        if the DEFAULT_PIPELINES_ENABLED setting is None (or missing).
        """
        project = Project.objects.create(name="Test Project for Processing Service", create_defaults=True)
        processing_service = project.processing_services.first()
        assert processing_service is not None
        # There should be at least two pipelines created by default
        self.assertGreaterEqual(processing_service.pipelines.count(), 2)
        # All pipelines should be enabled by default
        project_pipeline_configs = ProjectPipelineConfig.objects.filter(project=project)
        for config in project_pipeline_configs:
            self.assertTrue(
                config.enabled,
                f"Pipeline {config.pipeline.name} should be enabled for project {project.name}.",
            )

    @override_settings(
        DEFAULT_PROCESSING_SERVICE_NAME="Default Processing Service",
        DEFAULT_PROCESSING_SERVICE_ENDPOINT="http://ml_backend:2000/",  # should have at least two pipelines
        DEFAULT_PIPELINES_ENABLED=["constant"],
    )
    def test_existing_processing_service_new_project(self):
        """
        Create a new project, enable all pipelines.
        Create a 2nd project, ensure that the same processing service is used and only the enabled pipelines are
        registered.
        """
        enabled_pipelines = ["constant"]

        project_one = Project.objects.create(name="Test Project One", create_defaults=True)

        # Enable all pipelines for the first project
        ProjectPipelineConfig.objects.filter(project=project_one).update(enabled=True)

        project_two = Project.objects.create(name="Test Project Two", create_defaults=True)

        project_one_processing_service = project_one.processing_services.first()
        project_two_processing_service = project_two.processing_services.first()

        assert project_one_processing_service is not None
        assert project_two_processing_service is not None

        # Ensure only the same processing service instance is used (and they are not None)
        self.assertEqual(
            project_one_processing_service,
            project_two_processing_service,
            "Both projects should use the same processing service instance.",
        )

        # Ensure that only the enabled pipelines are enabled for the second project
        project_two_pipeline_configs = ProjectPipelineConfig.objects.filter(project=project_two)
        self.assertGreaterEqual(project_two_pipeline_configs.count(), 2, "Project should have at least two pipelines.")
        for config in project_two_pipeline_configs:
            if config.pipeline.slug in enabled_pipelines:
                self.assertTrue(
                    config.enabled,
                    f"Pipeline {config.pipeline.name} should be enabled for project {project_two.name}.",
                )
            else:
                self.assertFalse(
                    config.enabled,
                    f"Pipeline {config.pipeline.name} should not be enabled for project {project_two.name}.",
                )


class TestProjectListOverviewCounts(APITestCase):
    """The projects table gets per-project totals and activity dates, sortable, at a fixed query cost."""

    endpoint = "/api/v2/projects/"

    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner = User.objects.create_user(email="overview-owner@insectai.org")
        cls.member = User.objects.create_user(email="overview-member@insectai.org")
        cls.busy = Project.objects.create(name="Busy project", owner=cls.owner, create_defaults=False)
        cls.busy.members.add(cls.member)
        cls.empty = Project.objects.create(name="Empty project", owner=cls.owner, create_defaults=False)
        last_capture = datetime.datetime(2026, 6, 1, 23, 0)
        for name, captures, occurrences, timestamp in [
            ("Station A", 100, 10, last_capture),
            ("Station B", 50, 5, last_capture - datetime.timedelta(days=3)),
        ]:
            deployment = Deployment.objects.create(name=name, project=cls.busy)
            SourceImage.objects.create(deployment=deployment, project=cls.busy, timestamp=timestamp, path=name)
            # Set after create, which recalculates the cached counts from (no) captures.
            Deployment.objects.filter(pk=deployment.pk).update(captures_count=captures, occurrences_count=occurrences)
        cls.last_capture = last_capture

    def _rows(self, user: User | None = None, **params) -> list[dict]:
        self.client.force_authenticate(user)
        response = self.client.get(self.endpoint, {"with_counts": "true", **params})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()["results"]

    def test_counts_are_rolled_up_from_deployments(self):
        rows = {row["id"]: row for row in self._rows(self.owner)}
        busy, empty = rows[self.busy.pk], rows[self.empty.pk]
        self.assertEqual(
            (busy["deployments_count"], busy["captures_count"], busy["occurrences_count"], busy["members_count"]),
            (2, 150, 15, 2),
        )
        self.assertEqual(busy["last_capture_timestamp"][:16], self.last_capture.isoformat()[:16])
        self.assertEqual(
            (empty["deployments_count"], empty["captures_count"], empty["occurrences_count"], empty["members_count"]),
            (0, 0, 0, 1),
        )
        self.assertIsNone(empty["last_capture_timestamp"])
        self.assertIsNone(empty["last_occurrence_updated_at"])
        self.assertIsNone(empty["last_job_updated_at"])

    def test_taxa_observed_count_follows_each_projects_default_filters(self):
        """Distinct taxa above the project's score threshold, as on the project summary."""
        station = Deployment.objects.filter(project=self.busy).first()
        event = Event.objects.create(
            project=self.busy, deployment=station, group_by="2026-06-01", start=self.last_capture
        )
        moth, beetle, unsure = (Taxon.objects.create(name=f"Overview {name}") for name in ("moth", "beetle", "unsure"))
        for taxon, score in [(moth, 0.9), (moth, 0.8), (beetle, 0.9), (unsure, 0.1)]:
            Occurrence.objects.create(
                project=self.busy, deployment=station, event=event, determination=taxon, determination_score=score
            )
        rows = {row["id"]: row for row in self._rows(self.owner)}
        self.assertEqual(
            (rows[self.busy.pk]["taxa_observed_count"], rows[self.empty.pk]["taxa_observed_count"]), (2, 0)
        )

    def test_team_size_is_only_shown_to_those_who_can_see_the_team(self):
        """members_count follows the permission to open the team list, whether held through a role or directly."""
        superuser = User.objects.create_superuser(email="overview-admin@insectai.org", password="unused")
        # Granted the team list on one project without joining it.
        outsider = User.objects.create_user(email="overview-outsider@insectai.org")
        assign_perm(Project.Permissions.VIEW_USER_PROJECT_MEMBERSHIP, outsider, self.busy)
        for user, expected in [
            (None, (None, None)),
            (outsider, (2, None)),
            (self.member, (2, None)),
            (self.owner, (2, 1)),
            (superuser, (2, 1)),
        ]:
            rows = {row["id"]: row for row in self._rows(user)}
            with self.subTest(user=user):
                self.assertEqual((rows[self.busy.pk]["members_count"], rows[self.empty.pk]["members_count"]), expected)

    def test_totals_are_left_out_unless_asked_for(self):
        """The gallery gets the activity dates but none of the totals, apart from the station count."""
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = next(row for row in response.json()["results"] if row["id"] == self.busy.pk)
        self.assertEqual(row["deployments_count"], 2)
        self.assertEqual(row["last_capture_timestamp"][:16], self.last_capture.isoformat()[:16])
        for field in ["captures_count", "members_count", "taxa_observed_count", "location"]:
            self.assertNotIn(field, row)

    def test_location_ignores_stations_without_real_coordinates(self):
        stations = list(Deployment.objects.filter(project=self.busy).order_by("name"))
        Deployment.objects.filter(pk=stations[0].pk).update(latitude=45.0, longitude=-73.0)
        Deployment.objects.filter(pk=stations[1].pk).update(latitude=47.0, longitude=-71.0)
        Deployment.objects.create(name="Placeholder", project=self.busy, latitude=0, longitude=0)
        Deployment.objects.create(name="Unknown", project=self.busy)

        # The map asks for locations without the totals.
        response = self.client.get(self.endpoint, {"with_location": "true"})
        rows = {row["id"]: row for row in response.json()["results"]}
        busy, empty = rows[self.busy.pk], rows[self.empty.pk]
        self.assertNotIn("captures_count", busy)
        self.assertAlmostEqual(busy["location"]["latitude"], 46.0)
        self.assertAlmostEqual(busy["location"]["longitude"], -72.0)
        self.assertIsNone(empty["location"])

    def test_sorting_by_a_total_works_without_asking_for_totals(self):
        """A sort carried over from the table to the gallery still gets the totals it orders by."""
        response = self.client.get(self.endpoint, {"ordering": "-captures_count"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["results"][0]["id"], self.busy.pk)

    def test_counts_are_read_inside_the_list_query(self):
        """The tables behind the totals and dates are only read by the one list query, never once per project.

        The per-row permission lookups the list serializer already makes are outside this check.
        Cachalot is off so every query is seen.
        """
        for i in range(5):
            project = Project.objects.create(name=f"Extra {i}", owner=self.owner, create_defaults=False)
            Deployment.objects.create(name=f"Extra station {i}", project=project)
        disabled = cachalot_disabled()
        disabled.__enter__()
        try:
            with CaptureQueriesContext(connection) as queries:
                rows = self._rows()
        finally:
            # cachalot_disabled() does not restore itself when the block raises.
            disabled.__exit__(None, None, None)
        self.assertGreaterEqual(len(rows), 7)
        tables = ['"main_deployment"', '"main_userprojectmembership"', '"main_sourceimage"', '"jobs_job"']
        rollup_queries = [q["sql"] for q in queries if any(table in q["sql"] for table in tables)]
        self.assertEqual(len(rollup_queries), 1, rollup_queries)
        # Taxa are counted for the whole page in one grouped query, with each project's taxa filters prefetched.
        for marker in [
            'COUNT(DISTINCT "main_occurrence"."determination_id")',
            '"main_project_default_filters_include_taxa"',
        ]:
            self.assertEqual(sum(marker in q["sql"] for q in queries), 1, marker)
