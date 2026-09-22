import concurrent.futures
import datetime
import pathlib
import unittest
import uuid

from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory, APITestCase

from ami.base.serializers import reverse_with_params
from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Event,
    Identification,
    Occurrence,
    Project,
    SourceImage,
    SourceImageCollection,
    Taxon,
    TaxonRank,
    group_images_into_events,
)
from ami.ml.models import Algorithm, Pipeline, ProcessingService
from ami.ml.models.pipeline import collect_images, get_or_create_algorithm_and_category_map, save_results
from ami.ml.post_processing.small_size_filter import SmallSizeFilterTask
from ami.ml.schemas import (
    AlgorithmConfigResponse,
    AlgorithmReference,
    BoundingBox,
    ClassificationResponse,
    DetectionResponse,
    PipelineResultsResponse,
    SourceImageResponse,
)
from ami.tests.fixtures.main import (
    create_captures_from_files,
    create_processing_service,
    create_taxa,
    setup_test_project,
)
from ami.tests.fixtures.ml import ALGORITHM_CHOICES
from ami.users.models import User


class TestProcessingServiceAPI(APITestCase):
    """
    Test the Processing Services API endpoints.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Processing Service Test Project")

        self.user = User.objects.create_user(  # type: ignore
            email="testuser@insectai.org",
            is_staff=True,
        )
        self.factory = APIRequestFactory()

    def _create_processing_service(self, name: str, endpoint_url: str):
        processing_services_create_url = reverse_with_params(
            "api:processingservice-list", params={"project_id": self.project.pk}
        )
        self.client.force_authenticate(user=self.user)
        processing_service_data = {
            "name": name,
            "endpoint_url": endpoint_url,
        }
        resp = self.client.post(processing_services_create_url, processing_service_data)
        self.client.force_authenticate(user=None)
        self.assertEqual(resp.status_code, 201)
        return resp.json()["instance"]

    def _delete_processing_service(self, processing_service_id: int):
        processing_services_delete_url = reverse_with_params(
            "api:processing-service-detail", kwargs={"pk": processing_service_id}
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.delete(processing_services_delete_url)
        self.client.force_authenticate(user=None)
        self.assertEqual(resp.status_code, 204)
        return resp

    def _register_pipelines(self, processing_service_id, with_project_id=False):
        """
        Pins the frontend's call shape: usePopulateProcessingService.ts POSTs this
        endpoint with no project_id. with_project_id=True exercises the other shape.
        """
        params = {"project_id": self.project.pk} if with_project_id else {}
        processing_services_register_pipelines_url = reverse_with_params(
            "api:processingservice-register-pipelines", args=[processing_service_id], params=params
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(processing_services_register_pipelines_url)
        data = resp.json()
        self.assertEqual(data["success"], True)
        return data

    def test_create_processing_service(self):
        self._create_processing_service(
            name="Processing Service Test",
            endpoint_url="http://processing_service:2000",
        )

    def test_project_was_added(self):
        response = self._create_processing_service(
            name="Processing Service Test",
            endpoint_url="http://processing_service:2000",
        )
        processing_service_id = response["id"]
        processing_service = ProcessingService.objects.get(pk=processing_service_id)
        self.assertIn(self.project, processing_service.projects.all())

    def test_processing_service_pipeline_registration(self):
        """Pins the frontend's call shape: usePopulateProcessingService.ts POSTs register_pipelines
        with no project_id, relying on the endpoint resolving the user-visible set instead."""
        # register a processing service
        response = self._create_processing_service(
            name="Processing Service Test",
            endpoint_url="http://processing_service:2000",
        )
        processing_service_id = response["id"]

        # sync the processing service to create/add the associate pipelines
        response = self._register_pipelines(processing_service_id)
        processing_service = ProcessingService.objects.get(pk=processing_service_id)
        pipelines_queryset = processing_service.pipelines.all()

        self.assertEqual(pipelines_queryset.count(), len(response["pipelines"]))

    def test_processing_service_pipeline_registration_with_project_id(self):
        """The other call shape: register_pipelines also works when project_id is supplied."""
        response = self._create_processing_service(
            name="Processing Service Test With Project", endpoint_url="http://processing_service:2000"
        )
        processing_service_id = response["id"]

        response = self._register_pipelines(processing_service_id, with_project_id=True)
        processing_service = ProcessingService.objects.get(pk=processing_service_id)

        self.assertEqual(processing_service.pipelines.count(), len(response["pipelines"]))

    def test_check_status_without_project_id(self):
        """Pins the frontend's call shape: useTestProcessingServiceConnection.ts GETs status
        with no project_id."""
        service = ProcessingService.objects.create(name="Status Check Service", endpoint_url=None)
        service.projects.add(self.project)
        url = reverse_with_params("api:processingservice-status", args=[service.pk])

        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_create_processing_service_without_endpoint_url(self):
        """Test creating a ProcessingService without endpoint_url (pull mode)"""
        processing_services_create_url = reverse_with_params(
            "api:processingservice-list", params={"project_id": self.project.pk}
        )
        self.client.force_authenticate(user=self.user)
        processing_service_data = {
            "name": "Pull Mode Service",
            "description": "Service without endpoint",
        }
        resp = self.client.post(processing_services_create_url, processing_service_data)
        self.client.force_authenticate(user=None)

        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        # Check that endpoint_url is null
        self.assertIsNone(data["instance"]["endpoint_url"])

        # Check that status indicates service is not yet live (no heartbeat received)
        self.assertFalse(data["status"]["request_successful"])
        self.assertFalse(data["status"]["server_live"])
        self.assertIsNone(data["status"]["endpoint_url"])

    def test_get_status_with_null_endpoint_url(self):
        """Test get_status method when endpoint_url is None"""
        service = ProcessingService.objects.create(name="Pull Mode Service", endpoint_url=None)
        service.projects.add(self.project)

        status = service.get_status()

        self.assertFalse(status.request_successful)
        self.assertFalse(status.server_live)  # No heartbeat received yet = not live
        self.assertIsNone(status.endpoint_url)
        self.assertEqual(status.pipelines_online, [])

    def test_get_pipeline_configs_with_null_endpoint_url(self):
        """Test get_pipeline_configs method when endpoint_url is None"""
        service = ProcessingService.objects.create(name="Pull Mode Service", endpoint_url=None)

        configs = service.get_pipeline_configs()

        self.assertEqual(configs, [])


class TestProcessingServiceLastSeen(TestCase):
    """Test the last_seen, last_seen_live, and last_seen_latency fields."""

    def setUp(self):
        self.project = Project.objects.create(name="Last Seen Test Project")

    def test_mark_seen_sets_fields(self):
        """Test that mark_seen() sets last_seen and last_seen_live."""
        service = ProcessingService.objects.create(name="Async Worker", endpoint_url=None)
        service.projects.add(self.project)

        self.assertIsNone(service.last_seen)
        self.assertIsNone(service.last_seen_live)

        service.mark_seen(live=True)
        service.refresh_from_db()

        self.assertIsNotNone(service.last_seen)
        self.assertTrue(service.last_seen_live)

    def test_mark_seen_offline(self):
        """Test that mark_seen(live=False) sets last_seen_live to False."""
        service = ProcessingService.objects.create(name="Async Worker Offline", endpoint_url=None)

        service.mark_seen(live=False)
        service.refresh_from_db()

        self.assertIsNotNone(service.last_seen)
        self.assertFalse(service.last_seen_live)

    def test_get_status_updates_last_seen_for_sync_service(self):
        """Test that get_status() updates last_seen fields for sync services (even if endpoint is unreachable)."""
        service = ProcessingService.objects.create(name="Sync Service", endpoint_url="http://nonexistent-host:9999")
        service.projects.add(self.project)

        # get_status should update the fields even for unreachable endpoints
        service.get_status(timeout=1)
        service.refresh_from_db()

        self.assertIsNotNone(service.last_seen)
        self.assertFalse(service.last_seen_live)  # unreachable = not live
        self.assertIsNotNone(service.last_seen_latency)

    def test_model_has_last_seen_fields(self):
        """Test that ProcessingService model has last_seen fields and not last_checked."""
        service = ProcessingService.objects.create(name="Field Test Service", endpoint_url=None)
        service.mark_seen(live=True)
        service.refresh_from_db()

        # Verify new fields exist
        self.assertTrue(hasattr(service, "last_seen"))
        self.assertTrue(hasattr(service, "last_seen_live"))
        self.assertTrue(hasattr(service, "last_seen_latency"))

        # Verify old fields don't exist
        self.assertFalse(hasattr(service, "last_checked"))
        self.assertFalse(hasattr(service, "last_checked_live"))
        self.assertFalse(hasattr(service, "last_checked_latency"))


class ProcessingServicePublicPermissionsTestCase(TestCase):
    """
    Permission matrix for public vs. project-scoped ProcessingServices.

    A project-scoped service keeps its existing staff-only write rule (any
    active staff member, project membership not required). A public service
    instead requires the manage_public_processingservice platform permission
    (or a superuser) — plain staff status is not enough. All services use
    endpoint_url=None (pull-mode) so get_status()/create_pipelines() never
    make a real network call.
    """

    def setUp(self):
        self.staff = User.objects.create_user(email="staff-ps@example.com", password="testpass", is_staff=True)
        self.member = User.objects.create_user(email="member-ps@example.com", password="testpass")
        self.non_member = User.objects.create_user(email="nonmember-ps@example.com", password="testpass")
        self.superuser = User.objects.create_superuser(email="super-ps@example.com", password="testpass")
        self.public_manager = User.objects.create_user(
            email="manager-ps@example.com", password="testpass", is_staff=True
        )
        perm = Permission.objects.get(codename="manage_public_processingservice", content_type__app_label="ml")
        self.public_manager.user_permissions.add(perm)

        self.project = Project.objects.create(name="PS Test Project", create_defaults=False)
        self.project.members.add(self.member)

        self.public_service = ProcessingService.objects.create(
            name="Public Service", endpoint_url=None, is_public=True
        )
        self.scoped_service = ProcessingService.objects.create(name="Scoped Service", endpoint_url=None)
        self.scoped_service.projects.add(self.project)

        self.client = APIClient()

    def _detail_url(self, service):
        return f"/api/v2/ml/processing_services/{service.pk}/?project_id={self.project.pk}"

    def _status_url(self, service):
        return f"/api/v2/ml/processing_services/{service.pk}/status/?project_id={self.project.pk}"

    def _register_url(self, service):
        return f"/api/v2/ml/processing_services/{service.pk}/register_pipelines/?project_id={self.project.pk}"

    def _register_url_no_project(self, service):
        """Pins the frontend's call shape: usePopulateProcessingService.ts POSTs with no project_id."""
        return f"/api/v2/ml/processing_services/{service.pk}/register_pipelines/"

    # -- Update --

    def test_staff_can_update_scoped_service(self):
        self.client.force_authenticate(self.staff)
        response = self.client.patch(self._detail_url(self.scoped_service), {"name": "Renamed"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_staff_cannot_update_public_service(self):
        """Plain staff status is not enough for a public service."""
        self.client.force_authenticate(self.staff)
        response = self.client.patch(self._detail_url(self.public_service), {"name": "Hacked"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_cannot_update_scoped_service(self):
        """Project membership alone is not the write gate here — staff status is."""
        self.client.force_authenticate(self.member)
        response = self.client.patch(self._detail_url(self.scoped_service), {"name": "Hacked"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_can_update_public_service(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.patch(self._detail_url(self.public_service), {"name": "Renamed by super"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_public_manager_can_update_public_service(self):
        self.client.force_authenticate(self.public_manager)
        response = self.client.patch(self._detail_url(self.public_service), {"name": "Renamed"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_public_manager_can_still_update_scoped_service(self):
        """The public manager is also staff, so the existing staff-only rule still applies."""
        self.client.force_authenticate(self.public_manager)
        response = self.client.patch(self._detail_url(self.scoped_service), {"name": "Renamed"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # -- Delete --

    def test_staff_cannot_delete_public_service(self):
        self.client.force_authenticate(self.staff)
        response = self.client.delete(self._detail_url(self.public_service))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_delete_scoped_service(self):
        self.client.force_authenticate(self.staff)
        response = self.client.delete(self._detail_url(self.scoped_service))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_public_manager_can_delete_public_service(self):
        self.client.force_authenticate(self.public_manager)
        response = self.client.delete(self._detail_url(self.public_service))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_public_manager_can_delete_public_service_with_include_public_false(self):
        """
        include_public=false must not make get_queryset() 404 the very row being
        deleted: it governs the list action's default scope, not whether a public
        row can be looked up for a detail action.
        """
        self.client.force_authenticate(self.public_manager)
        url = f"{self._detail_url(self.public_service)}&include_public=false"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # -- Retrieve / list visibility --

    def test_anonymous_can_retrieve_public_service(self):
        response = self.client.get(self._detail_url(self.public_service))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_member_can_see_public_service(self):
        self.client.force_authenticate(self.non_member)
        response = self.client.get(f"/api/v2/ml/processing_services/?project_id={self.project.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(self.public_service.pk, ids)

    def test_is_public_is_reported_in_the_response(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self._detail_url(self.public_service))
        self.assertTrue(response.json()["is_public"])

    def test_is_public_cannot_be_set_through_the_api(self):
        self.client.force_authenticate(self.staff)
        self.client.patch(self._detail_url(self.scoped_service), {"is_public": True})
        self.scoped_service.refresh_from_db()
        self.assertFalse(self.scoped_service.is_public)

    def test_user_permissions_include_update_delete_for_public_manager_only(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self._detail_url(self.public_service))
        self.assertNotIn("update", response.json()["user_permissions"])

        self.client.force_authenticate(self.public_manager)
        response = self.client.get(self._detail_url(self.public_service))
        perms = response.json()["user_permissions"]
        self.assertIn("update", perms)
        self.assertIn("delete", perms)

    # -- status (a read-type action; open to everyone like any other safe method) --

    def test_anonymous_can_check_status_of_public_service(self):
        response = self.client.get(self._status_url(self.public_service))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_member_can_check_status_of_scoped_service(self):
        self.client.force_authenticate(self.non_member)
        response = self.client.get(self._status_url(self.scoped_service))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # -- register_pipelines --

    def test_staff_cannot_register_pipelines_on_public_service(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(self._register_url(self.public_service))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_register_pipelines_on_scoped_service(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(self._register_url(self.scoped_service))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_public_manager_can_register_pipelines_on_public_service(self):
        self.client.force_authenticate(self.public_manager)
        response = self.client.post(self._register_url(self.public_service))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_member_cannot_register_pipelines_on_scoped_service(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(self._register_url(self.scoped_service))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_public_manager_can_register_pipelines_on_public_service_without_project_id(self):
        """The platform-permission bypass works the same whether or not project_id is supplied."""
        self.client.force_authenticate(self.public_manager)
        response = self.client.post(self._register_url_no_project(self.public_service))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_include_public_false_does_not_hide_a_public_service_from_retrieve(self):
        """
        include_public governs the list action's default scope, not whether a
        specific public row exists. ?include_public=false on a detail URL must not
        404 a public service the caller is otherwise allowed to see.
        """
        url = f"{self._detail_url(self.public_service)}&include_public=false"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ProcessingServiceIncludePublicParamTestCase(TestCase):
    """?include_public toggles whether public services appear alongside a project's own."""

    def setUp(self):
        self.user = User.objects.create_user(email="ps-scope-user@example.com", password="testpass")
        self.project = Project.objects.create(name="PS Scope Project", create_defaults=False)
        self.project.members.add(self.user)
        self.other_project = Project.objects.create(name="PS Other Scope Project", create_defaults=False)

        self.scoped_service = ProcessingService.objects.create(name="PS Scoped", endpoint_url=None)
        self.scoped_service.projects.add(self.project)
        self.public_service = ProcessingService.objects.create(name="PS Public", endpoint_url=None, is_public=True)
        # A public service can also be linked to an unrelated project without appearing twice.
        self.public_service.projects.add(self.other_project)

        self.hidden_service = ProcessingService.objects.create(name="PS Hidden with no project", endpoint_url=None)

        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _list_ids(self, **params):
        params["project_id"] = self.project.pk
        query = "&".join(f"{k}={v}" for k, v in params.items())
        response = self.client.get(f"/api/v2/ml/processing_services/?{query}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()["results"]

    def test_public_services_included_by_default(self):
        ids = {row["id"] for row in self._list_ids()}
        self.assertEqual(ids, {self.scoped_service.pk, self.public_service.pk})

    def test_include_public_false_hides_public_services(self):
        ids = {row["id"] for row in self._list_ids(include_public="false")}
        self.assertEqual(ids, {self.scoped_service.pk})

    def test_include_public_invalid_value_returns_400(self):
        response = self.client.get(
            f"/api/v2/ml/processing_services/?project_id={self.project.pk}&include_public=notabool"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # The no-duplication guarantee for a public row linked to several projects is a
    # property of the shared for_project()/visible_for_user() code, tested once at
    # the querySet level (TaxaListForProjectQuerySetTestCase) and once at the API
    # level, as a superuser, in TaxaListIncludePublicParamTestCase — no need to
    # repeat it here for ProcessingService.

    def test_hidden_zero_project_service_is_invisible_to_non_superuser(self):
        ids = {row["id"] for row in self._list_ids()}
        self.assertNotIn(self.hidden_service.pk, ids)


class ProcessingServiceProjectsFieldVisibilityTestCase(TestCase):
    """
    A public service bypasses the draft-project visibility filter that would
    otherwise hide it, so its own `projects` field must not become a side channel
    for disclosing a draft project's id to someone who can't see that project.
    """

    def setUp(self):
        self.owner = User.objects.create_user(email="ps-projfield-owner@example.com", password="testpass")
        self.member = User.objects.create_user(email="ps-projfield-member@example.com", password="testpass")
        self.draft_project = Project.objects.create(
            name="PS Projfield Draft Project", owner=self.owner, draft=True, create_defaults=False
        )
        self.draft_project.members.add(self.member)
        self.public_project = Project.objects.create(name="PS Projfield Public Project", create_defaults=False)

        self.public_service = ProcessingService.objects.create(
            name="PS Cross-Project Public Service", endpoint_url=None, is_public=True
        )
        self.public_service.projects.add(self.draft_project, self.public_project)

        self.client = APIClient()

    def _detail_url(self):
        return f"/api/v2/ml/processing_services/{self.public_service.pk}/?project_id={self.public_project.pk}"

    def test_anonymous_sees_only_the_non_draft_project_id(self):
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["projects"], [self.public_project.pk])

    def test_draft_project_member_sees_both_project_ids(self):
        self.client.force_authenticate(self.member)
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.json()["projects"]), {self.draft_project.pk, self.public_project.pk})


@override_settings(CACHALOT_ENABLED=False)
class ProcessingServiceQueryCountTestCase(APITestCase):
    """
    Pins the current query count for ProcessingServiceViewSet.list on a mixed
    public/scoped, multi-row fixture, so a regression that adds queries is
    noticed. This does not certify the absence of per-row queries — it only
    catches a further increase from where things stand today.
    """

    def setUp(self):
        self.user = User.objects.create_user(email="ps-qc-user@example.com", password="testpass")
        self.project = Project.objects.create(name="PS QC Project", create_defaults=False)
        self.project.members.add(self.user)
        for i in range(3):
            scoped = ProcessingService.objects.create(name=f"PS Scoped {i}", endpoint_url=None)
            scoped.projects.add(self.project)
        for i in range(2):
            ProcessingService.objects.create(name=f"PS Public {i}", endpoint_url=None, is_public=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_query_count(self):
        from cachalot.api import cachalot_disabled

        url = f"/api/v2/ml/processing_services/?project_id={self.project.pk}"
        with cachalot_disabled(), CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["results"]), 5)
        # 34 (previous baseline) down to 21: add_processingservice_permissions() no
        # longer runs the M2M membership check or the guardian get_perms() lookup
        # per non-public row (no per-project *_processingservice guardian permission
        # exists, so that branch could only ever fire for a superuser, which a plain
        # attribute check covers for free); get_projects() adds back one query per
        # request (not per row) for the draft-project-id visibility filter.
        self.assertEqual(len(ctx.captured_queries), 21)


class TestProjectPipelineRegistrationUpdatesLastSeen(APITestCase):
    """Test that async pipeline registration updates last_seen on the processing service."""

    def setUp(self):
        from ami.users.roles import ProjectManager, create_roles_for_project

        self.user = User.objects.create_user(email="lastseen@example.com")  # type: ignore
        self.project = Project.objects.create(name="Last Seen Project", owner=self.user, create_defaults=False)
        create_roles_for_project(self.project)
        ProjectManager.assign_user(self.user, self.project)

    def test_pipeline_registration_marks_service_as_seen(self):
        """Test that POSTing to the pipeline registration endpoint marks the service as last_seen_live."""
        url = f"/api/v2/projects/{self.project.pk}/pipelines/"
        payload = {
            "processing_service_name": "AsyncTestWorker",
            "pipelines": [],
        }

        self.client.force_authenticate(user=self.user)
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 201)

        service = ProcessingService.objects.get(name="AsyncTestWorker")
        self.assertIsNotNone(service.last_seen)
        self.assertTrue(service.last_seen_live)

    def test_repeated_registration_updates_last_seen(self):
        """Test that re-registering updates the last_seen timestamp."""
        url = f"/api/v2/projects/{self.project.pk}/pipelines/"
        payload = {
            "processing_service_name": "AsyncTestWorkerRepeat",
            "pipelines": [],
        }

        self.client.force_authenticate(user=self.user)

        # First registration
        self.client.post(url, payload, format="json")
        service = ProcessingService.objects.get(name="AsyncTestWorkerRepeat")
        first_seen = service.last_seen

        # Second registration
        self.client.post(url, payload, format="json")
        service.refresh_from_db()
        second_seen = service.last_seen

        self.assertIsNotNone(first_seen)
        self.assertIsNotNone(second_seen)
        self.assertGreaterEqual(second_seen, first_seen)


class TestPipelineWithProcessingService(TestCase):
    def test_run_pipeline_with_errors_from_processing_service(self):
        """
        Run a real pipeline and verify that if an error occurs for one image, the error is logged to JobLog.
        """
        from ami.jobs.models import Job, JobLog

        # Setup test project, images, and job
        project, deployment = setup_test_project()
        captures = create_captures_from_files(deployment, skip_existing=False)
        test_images = [image for image, frame in captures]
        processing_service_instance = create_processing_service(project)
        pipeline = processing_service_instance.pipelines.all().get(slug="constant")
        job = Job.objects.create(project=project, name="Test Job Real Pipeline Error Handling", pipeline=pipeline)

        # Simulate an error by passing an invalid image (e.g., missing file or corrupt)
        # Here, we manually set the path of one image to a non-existent file
        error_image = test_images[0]
        error_image.path = "/tmp/nonexistent_image.jpg"
        error_image.save()
        images = [error_image] + test_images[1:2]  # Only two images for brevity

        # Run the pipeline and catch any error
        try:
            pipeline.process_images(images, job_id=job.pk, project_id=project.pk)
        except Exception:
            pass  # Expected if the backend raises

        job.refresh_from_db()
        stderr_logs = list(
            JobLog.objects.filter(job=job, level__in=["ERROR", "CRITICAL"]).values_list("message", flat=True)
        )
        # Check that an error message mentioning the failed image is present
        assert any(
            "Failed to process" in log for log in stderr_logs
        ), f"Expected error message in job logs, got: {stderr_logs}"

    def setUp(self):
        self.project, self.deployment = setup_test_project()
        self.captures = create_captures_from_files(self.deployment, skip_existing=False)
        self.test_images = [image for image, frame in self.captures]
        self.processing_service_instance = create_processing_service(self.project)
        self.processing_service = self.processing_service_instance
        assert self.processing_service_instance.pipelines.exists()
        self.pipeline = self.processing_service_instance.pipelines.all().get(slug="constant")

    def test_run_pipeline(self):
        # Send images to Processing Service to process and return detections
        assert self.pipeline
        pipeline_response = self.pipeline.process_images(self.test_images, job_id=None, project_id=self.project.pk)
        assert pipeline_response.detections

    def test_created_category_maps(self):
        # Send images to ML backend to process and return detections
        assert self.pipeline
        pipeline_response = self.pipeline.process_images(self.test_images, project_id=self.project.pk)
        save_results(pipeline_response, return_created=True)

        source_images = SourceImage.objects.filter(pk__in=[image.id for image in pipeline_response.source_images])
        detections = Detection.objects.filter(source_image__in=source_images).select_related(
            "detection_algorithm",
            "detection_algorithm__category_map",
        )
        assert detections.count() > 0
        for detection in detections:
            # No detection algorithm should have category map at this time (but this may change!)
            assert detection.detection_algorithm
            assert detection.detection_algorithm.category_map is None

            # Ensure that all classification algorithms have a category map
            classification_taxa = set()
            for classification in detection.classifications.all().select_related(
                "algorithm",
                "algorithm__category_map",
            ):
                assert classification.algorithm is not None
                assert classification.category_map is not None
                assert classification.algorithm.category_map == classification.category_map

                _, top_score = list(classification.predictions(sort=True))[0]
                assert top_score == classification.score

                top_taxon, top_taxon_score = list(classification.predictions_with_taxa(sort=True))[0]
                assert top_taxon == classification.taxon
                assert top_taxon_score == classification.score

                classification_taxa.add(top_taxon)

            # Check the occurrence determination taxon
            assert detection.occurrence
            assert detection.occurrence.determination in classification_taxa

    def test_missing_category_map(self):
        # Test that an exception is raised if a classification algorithm is missing a category map
        from ami.ml.exceptions import PipelineNotConfigured

        # Get the response from the /info endpoint
        pipeline_configs = self.processing_service.get_pipeline_configs()

        # Assert that there is a least one classification algorithm with a category map
        self.assertTrue(
            any(
                algo.task_type in Algorithm.classification_task_types and algo.category_map is not None
                for pipeline in pipeline_configs
                for algo in pipeline.algorithms
            ),
            "Expected pipeline to have at least one classification algorithm with a category map",
        )

        # Remove the category map from one of the classification algorithms
        for pipeline_config in pipeline_configs:
            for algorithm in pipeline_config.algorithms:
                if algorithm.task_type in Algorithm.classification_task_types and algorithm.category_map is not None:
                    algorithm.category_map = None
                    # Change the key to ensure it's treated as a new algorithm
                    algorithm.key = "missing-category-map-classifier"
                    algorithm.name = "Classifier with Missing Category Map"
                    break

        with self.assertRaises(
            PipelineNotConfigured,
            msg="Expected an exception to be raised if a classification algorithm is missing a category map",
        ):
            self.processing_service.create_pipelines(pipeline_configs=pipeline_configs)

    def test_alignment_of_predictions_and_category_map(self):
        # Ensure that the scores and labels are aligned
        pipeline = self.processing_service_instance.pipelines.all().get(slug="random-detection-random-species")
        pipeline_response = pipeline.process_images(self.test_images, project_id=self.project.pk)
        results = save_results(pipeline_response, return_created=True)
        assert results is not None, "Expected results to be returned in a PipelineSaveResults object"
        assert results.classifications, "Expected classifications to be returned in the results"
        for classification in results.classifications:
            assert classification.scores
            taxa_with_scores = list(classification.predictions_with_taxa(sort=True))
            assert taxa_with_scores
            assert classification.score == taxa_with_scores[0][1]
            assert classification.taxon == taxa_with_scores[0][0]

    def test_top_n_alignment(self):
        # Ensure that the top_n parameter works
        pipeline = self.processing_service_instance.pipelines.all().get(slug="random-detection-random-species")
        pipeline_response = pipeline.process_images(self.test_images, project_id=self.project.pk)
        results = save_results(pipeline_response, return_created=True)
        assert results is not None, "Expecected results to be returned in a PipelineSaveResults object"
        assert results.classifications, "Expected classifications to be returned in the results"
        for classification in results.classifications:
            top_n = classification.top_n(n=3)
            assert classification.score == top_n[0]["score"]
            assert classification.taxon == top_n[0]["taxon"]

    def test_pipeline_reprocessing(self):
        """
        Test that reprocessing the same images with differet pipelines does not create duplicate
        detections. The 2 pipelines used are a random detection + random species classifier, and a
        constant species classifier.
        """
        if not self.project.feature_flags.reprocess_existing_detections:
            self.project.feature_flags.reprocess_existing_detections = True
            self.project.save()

        # Process the images once
        pipeline_one = self.processing_service_instance.pipelines.all().get(slug="random-detection-random-species")
        num_classifiers_pipeline_one = pipeline_one.algorithms.filter(task_type="classification").count()
        pipeline_response = pipeline_one.process_images(self.test_images, project_id=self.project.pk)
        results = save_results(pipeline_response, return_created=True)
        assert results is not None, "Expected results to be returned in a PipelineSaveResults object"
        assert results.detections, "Expected detections to be returned in the results"
        num_initial_detections = len(results.detections)

        # This particular pipeline produces 2 classifications per detection
        for det in results.detections:
            num_classifications = det.classifications.count()
            self.assertEqual(
                num_classifications,
                num_classifiers_pipeline_one,
                f"Expected {num_classifiers_pipeline_one} classifications per detection "
                "(random species and random binary classifier).",
            )

        source_images = SourceImage.objects.filter(pk__in=[image.id for image in pipeline_response.source_images])
        detections = Detection.objects.filter(source_image__in=source_images).select_related(
            "detection_algorithm",
            "detection_algorithm__category_map",
        )
        initial_detection_ids = sorted([det.pk for det in detections])
        assert detections.count() > 0

        # Reprocess the same images using a different pipeline
        pipeline_two = self.processing_service_instance.pipelines.all().get(slug="constant")
        num_classifiers_pipeline_two = pipeline_two.algorithms.filter(task_type="classification").count()
        pipeline_response = pipeline_two.process_images(self.test_images, project_id=self.project.pk)
        reprocessed_results = save_results(pipeline_response, return_created=True)
        assert reprocessed_results is not None, "Expected results to be returned in a PipelineSaveResults object"
        assert reprocessed_results.detections, "Expected detections to be returned in the results"
        num_reprocessed_detections = len(reprocessed_results.detections)
        self.assertEqual(
            num_reprocessed_detections,
            num_initial_detections,
            "Expected the same number of detections after reprocessing with a different pipeline.",
        )

        source_images = SourceImage.objects.filter(pk__in=[image.id for image in pipeline_response.source_images])
        detections = Detection.objects.filter(source_image__in=source_images).select_related(
            "detection_algorithm",
            "detection_algorithm__category_map",
        )

        # Check detections were re-processed, and not re-created
        reprocessed_detection_ids = sorted([det.pk for det in detections])
        assert initial_detection_ids == reprocessed_detection_ids, (
            "Expected the same detections to be returned after reprocessing with a different pipeline, "
            f"but found {initial_detection_ids} != {reprocessed_detection_ids}"
        )

        # The constant pipeline produces 1 classification per detection (added to the existing classifications)
        for detection in detections:
            self.assertEqual(
                detection.classifications.count(),
                num_classifiers_pipeline_one + num_classifiers_pipeline_two,
                f"Expected {num_classifiers_pipeline_one + num_classifiers_pipeline_two} "
                "classifications per detection (2 random classifiers + constant classifier).",
            )


class TestPipeline(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Test Project")
        # Create test images and collection
        self.test_images = [
            SourceImage.objects.create(path="test1-20240101000000.jpg"),
            SourceImage.objects.create(path="test2-20240101001000.jpg"),
        ]
        self.image_collection = SourceImageCollection.objects.create(
            name="Test Collection",
            project=self.project,
        )
        self.image_collection.images.set(self.test_images)

        # Create test pipeline and algorithms
        self.pipeline = Pipeline.objects.create(
            name="Test Pipeline (Random)",
        )
        self.pipeline_two = Pipeline.objects.create(
            name="Test Pipeline (Constant)",
        )

        self.algorithms = {
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.pipeline.algorithms.set(
            [
                self.algorithms["random-detector"],
                self.algorithms["random-binary-classifier"],
                self.algorithms["random-species-classifier"],
            ]
        )
        self.pipeline_two.algorithms.set(
            [
                self.algorithms["random-detector"],
                self.algorithms["random-binary-classifier"],
                self.algorithms["constant-species-classifier"],
            ]
        )

    def test_create_pipeline(self):
        assert self.pipeline.slug.startswith("test-pipeline")
        self.assertEqual(self.pipeline.algorithms.count(), 3)
        self.assertEqual(self.pipeline_two.algorithms.count(), 3)

        for algorithm in self.pipeline.algorithms.all():
            assert isinstance(algorithm, Algorithm)
            self.assertIn(algorithm.key, [algo.key for algo in ALGORITHM_CHOICES.values()])

    def test_collect_images(self):
        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        assert len(images) == 2

    def test_collect_images_prefetches_deployment_and_data_source(self):
        """
        collect_images() must hand back SourceImage rows with deployment and
        deployment.data_source already joined, so the downstream queue_images_to_nats
        loop doesn't trigger N+1 FK lookups inside image.url() (see issue #1321).
        """
        from ami.main.models import S3StorageSource

        data_source = S3StorageSource.objects.create(
            name="ds-prefetch-test",
            bucket="prefetch-bucket",
            access_key="x",
            secret_key="y",  # noqa: S106 - fixture value, never used as a real credential
            public_base_url="https://example.invalid/",
            project=self.project,
        )
        deployment = Deployment.objects.create(
            name="prefetch-deployment", project=self.project, data_source=data_source
        )
        images = [
            SourceImage.objects.create(path=f"prefetch-{i}.jpg", deployment=deployment, project=self.project)
            for i in range(3)
        ]
        collection = SourceImageCollection.objects.create(project=self.project, name="prefetch-collection")
        collection.images.set(images)

        collected = list(collect_images(collection=collection, pipeline=self.pipeline))
        self.assertEqual(len(collected), 3)

        # Accessing deployment.data_source on the returned images should
        # require zero extra queries because select_related joined both.
        with self.assertNumQueries(0):
            for image in collected:
                self.assertEqual(image.deployment_id, deployment.pk)
                self.assertEqual(image.deployment.data_source_id, data_source.pk)
                self.assertEqual(image.deployment.data_source.public_base_url, "https://example.invalid/")

    def fake_pipeline_results(
        self,
        source_images: list[SourceImage],
        pipeline: Pipeline,
        alt_species_classifier: AlgorithmConfigResponse | None = None,
    ):
        # @TODO use the pipeline passed in to get the algorithms
        source_image_results = [SourceImageResponse(id=image.pk, url=image.path) for image in source_images]
        detector = ALGORITHM_CHOICES["random-detector"]
        binary_classifier = ALGORITHM_CHOICES["random-binary-classifier"]
        assert binary_classifier.category_map

        if alt_species_classifier is None:
            species_classifier = ALGORITHM_CHOICES["random-species-classifier"]
        else:
            species_classifier = alt_species_classifier
        assert species_classifier.category_map

        detection_results = [
            DetectionResponse(
                source_image_id=image.pk,
                bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
                inference_time=0.4,
                algorithm=AlgorithmReference(
                    name=detector.name,
                    key=detector.key,
                ),
                timestamp=datetime.datetime.now(),
                classifications=[
                    ClassificationResponse(
                        classification=binary_classifier.category_map.labels[0],
                        labels=binary_classifier.category_map.labels,
                        scores=[0.9213],
                        algorithm=AlgorithmReference(
                            name=binary_classifier.name,
                            key=binary_classifier.key,
                        ),
                        timestamp=datetime.datetime.now(),
                        terminal=False,
                    ),
                    ClassificationResponse(
                        classification=species_classifier.category_map.labels[0],
                        labels=species_classifier.category_map.labels,
                        scores=[0.64333],
                        algorithm=AlgorithmReference(
                            name=species_classifier.name,
                            key=species_classifier.key,
                        ),
                        timestamp=datetime.datetime.now(),
                        terminal=True,
                    ),
                ],
            )
            for image in self.test_images
        ]
        fake_results = PipelineResultsResponse(
            pipeline=pipeline.slug,
            algorithms={
                detector.key: detector,
                binary_classifier.key: binary_classifier,
                species_classifier.key: species_classifier,
            },
            total_time=0.01,
            source_images=source_image_results,
            detections=detection_results,
        )
        return fake_results

    def test_save_results(self):
        results = self.fake_pipeline_results(self.test_images, self.pipeline)
        save_results(results)

        for image in self.test_images:
            image.save()
            self.assertEqual(image.detections_count, 1)

        # @TODO test the cached counts for detections, etc are updated on Events, Deployments, etc.

    def test_skip_existing_when_all_matching(self):
        """
        When processing images, skip images that have already been processed by the same set of algorithms.
        (must be the same detection algorithm and all classification algorithms)
        """

        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        total_images = len(images)
        self.assertEqual(total_images, self.image_collection.images.count())

        created = save_results(self.fake_pipeline_results(images, self.pipeline), return_created=True)
        assert created, "Expected created objects to be returned in a PipelineSaveResults object"

        # Collect all detection algorithms used on the detections
        detections = created.detections
        detection_algos_used = {
            detection.detection_algorithm.name for detection in detections if detection.detection_algorithm
        }
        # detection_algos_used = set(Detection.objects.all().values_list("detection_algorithm__name", flat=True))

        # Assert it was only one algorithm, and it was the one we used
        self.assertEqual(
            detection_algos_used, {self.algorithms["random-detector"].name}, "Wrong detection algorithm used."
        )

        # Collect all classification algorithms used on the classifications
        classifications = created.classifications
        classification_algos_used = {
            classification.algorithm.name for classification in classifications if classification.algorithm
        }
        # classification_algos_used = set(Classification.objects.all().values_list("algorithm__name", flat=True))
        # Assert it was only one algorithm, and it was the one we used
        self.assertEqual(
            classification_algos_used,
            {self.algorithms["random-species-classifier"].name, self.algorithms["random-binary-classifier"].name},
            "Wrong classification algorithms used.",
        )

        images_again = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, 0)

    def test_skip_existing_with_new_detector(self):
        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        total_images = len(images)
        self.assertEqual(total_images, self.image_collection.images.count())
        pipeline_response = self.fake_pipeline_results(images, self.pipeline)
        save_results(pipeline_response)
        # Find the fist algo used where task_type is classification
        classifiers = [algo for algo in pipeline_response.algorithms.values() if algo.task_type == "classification"]
        last_classifier = Algorithm.objects.get(key=classifiers[-1].key)
        self.pipeline.algorithms.set(
            [
                Algorithm.objects.create(name="NEW Object Detector 2.0"),
                last_classifier,
            ]
        )
        images_again = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, total_images)

    @unittest.skip("Not implemented yet")
    def test_skip_existing_with_new_classifier(self):
        """
        @TODO add support for skipping the detection model if only the classifier has changed.
        """
        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        total_images = len(images)
        self.assertEqual(total_images, self.image_collection.images.count())
        pipeline_response = self.fake_pipeline_results(images, self.pipeline)
        # Find the fist algo used where task_type is detection
        first_detector_in_response = next(
            algo for algo in pipeline_response.algorithms.values() if algo.task_type == "detection"
        )
        first_detector = Algorithm.objects.get(key=first_detector_in_response.key)
        save_results(pipeline_response)
        self.pipeline.algorithms.set(
            [
                first_detector,
                Algorithm.objects.create(name="NEW Classifier 2.0"),
            ]
        )
        images_again = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, total_images)

    @unittest.skip("Not implemented yet")
    def test_skip_existing_per_batch_during_processing(self):
        # Send the same batch to two simultaneous processing pipelines
        # @TODO this needs to test the `process_images()` function with a real pipeline
        # @TODO enable test when a pipeline is added to the CI environment in PR #576
        pass

    def test_unknown_algorithm_returned_by_processing_service(self):
        """
        Test that unknown algorithms returned by the processing service are handled correctly.

        Previously we allowed unknown algorithms to be returned by the pipeline,
        now all algorithms must be registered first from the processing service's /info
        endpoint.
        """
        fake_results = self.fake_pipeline_results(self.test_images, self.pipeline)

        new_detector = AlgorithmConfigResponse(
            name="Unknown Detector 5.1b-mobile", key="unknown-detector", task_type="detection"
        )
        new_classifier = AlgorithmConfigResponse(
            name="Unknown Classifier 3.0b-mega", key="unknown-classifier", task_type="classification"
        )

        fake_results.algorithms[new_detector.key] = new_detector
        fake_results.algorithms[new_classifier.key] = new_classifier

        for detection in fake_results.detections:
            detection.algorithm = AlgorithmReference(name=new_detector.name, key=new_detector.key)

            for classification in detection.classifications:
                classification.algorithm = AlgorithmReference(name=new_classifier.name, key=new_classifier.key)

        current_total_algorithm_count = Algorithm.objects.count()

        # Ensure an exception is raised that a new algorithm was not
        # pre-registered from the /info endpoint
        from ami.ml.exceptions import PipelineNotConfigured

        with self.assertRaises(PipelineNotConfigured):
            save_results(fake_results)

        # Ensure no new algorithms were added to the database
        new_algorithm_count = Algorithm.objects.count()
        self.assertEqual(new_algorithm_count, current_total_algorithm_count)

        # Ensure new algorithms were also added to the pipeline

    def test_yes_reprocess_if_new_terminal_algorithm_same_intermediate(self):
        """
        Test two pipelines with the same detector and same moth/non-moth classifier, but a new species classifier.

        The first pipeline should process the images and save the results.
        The second pipeline should reprocess the images.
        """

        images = list(collect_images(collection=self.image_collection, pipeline=self.pipeline))
        assert len(images), "No images to process"

        detector = Algorithm.objects.get(key="random-detector")
        binary_classifier = Algorithm.objects.get(key="random-binary-classifier")
        old_species_classifier = Algorithm.objects.get(key="random-species-classifier")

        Detection.objects.all().delete()
        results = save_results(self.fake_pipeline_results(images, self.pipeline), return_created=True)
        assert results is not None, "Expecected results to be returned in a PipelineSaveResults object"

        for raw_detection in results.detections:
            self.assertEqual(raw_detection.detection_algorithm, detector)

        # Ensure all results have the binary classifier and the old species classifier
        for saved_detection in Detection.objects.all():
            self.assertEqual(saved_detection.detection_algorithm, detector)
            # Assert that the binary classifier was used
            self.assertTrue(
                saved_detection.classifications.filter(algorithm=binary_classifier).exists(),
                "Binary classifier not used in first run",
            )
            # Assert that the old species classifier was used
            self.assertTrue(
                saved_detection.classifications.filter(algorithm=old_species_classifier).exists(),
                "Old species classifier not used in first run",
            )

        # Get another species classifier
        new_species_classifier_key = "constant-species-classifier"
        new_species_classifier = Algorithm.objects.get(key=new_species_classifier_key)
        # new_species_classifier_response = ALGORITHM_CHOICES[new_species_classifier_key]

        # Create a new pipeline with the same detector and the new species classifier
        new_pipeline = Pipeline.objects.create(
            name="New Pipeline",
        )

        new_pipeline.algorithms.set(
            [
                detector,
                binary_classifier,
                new_species_classifier,
            ]
        )

        # Process the images with the new pipeline
        images_again = list(collect_images(collection=self.image_collection, pipeline=new_pipeline))
        remaining_images_to_process = len(images_again)
        self.assertEqual(remaining_images_to_process, len(images), "Images not re-processed with new pipeline")

    def test_project_pipeline_config(self):
        """
        Test the default_config for a pipeline, as well as the project pipeline config.
        Ensure the project pipeline parameters override the pipeline defaults.
        """
        from ami.ml.models import ProjectPipelineConfig
        from ami.ml.schemas import PipelineRequestConfigParameters

        # Add config to the pipeline & project
        self.pipeline.default_config = PipelineRequestConfigParameters({"test_param": "test_value"})
        self.pipeline.save()
        self.project_pipeline_config = ProjectPipelineConfig.objects.create(
            project=self.project,
            pipeline=self.pipeline,
            config={"test_param": "project_value"},
        )
        self.project_pipeline_config.save()

        # Check the final config
        default_config = self.pipeline.get_config()
        self.assertEqual(default_config["test_param"], "test_value")
        final_config = self.pipeline.get_config(self.project.pk)
        self.assertEqual(final_config["test_param"], "project_value")

    def test_image_with_null_detection(self):
        """
        Test saving results for a pipeline that returns null detections for some images.
        """
        image = self.test_images[0]
        results = self.fake_pipeline_results([image], self.pipeline)

        # Manually change the results for a single image to a list of empty detections
        results.detections = []

        save_results(results)

        image.save()
        self.assertEqual(image.get_detections_count(), 0)  # detections_count should exclude null detections
        total_num_detections = image.detections.distinct().count()
        self.assertEqual(total_num_detections, 1)

        was_processed = image.get_was_processed()
        self.assertEqual(was_processed, True)

        # Also test filtering by algorithm
        was_processed = image.get_was_processed(algorithm_key="random-detector")
        self.assertEqual(was_processed, True)

    def test_filter_processed_images_skips_null_only_image(self):
        """
        An image with only null detections (processed, nothing found) should be
        skipped by filter_processed_images — it doesn't need reprocessing.
        """
        from ami.ml.models.pipeline import filter_processed_images

        image = self.test_images[0]
        detector = self.algorithms["random-detector"]

        # Simulate a previous run that found nothing: create a null detection
        Detection.objects.create(
            source_image=image,
            detection_algorithm=detector,
            bbox=None,
        )

        result = list(filter_processed_images([image], self.pipeline))
        self.assertEqual(result, [], "Image with only null detections should be skipped")

    def test_filter_processed_images_yields_image_with_null_and_real_unclassified(self):
        """
        An image with BOTH a null detection AND a real detection lacking classifications
        should NOT be skipped — the real detection still needs to be classified.
        """
        from ami.ml.models.pipeline import filter_processed_images

        image = self.test_images[0]
        detector = self.algorithms["random-detector"]

        # Null detection from a prior empty run
        Detection.objects.create(
            source_image=image,
            detection_algorithm=detector,
            bbox=None,
        )
        # Real detection with no classification yet
        Detection.objects.create(
            source_image=image,
            detection_algorithm=detector,
            bbox=[0.1, 0.2, 0.3, 0.4],
        )

        result = list(filter_processed_images([image], self.pipeline))
        self.assertEqual(result, [image], "Image with real unclassified detections should be yielded")

    def test_filter_processed_images_skips_null_and_fully_classified(self):
        """
        An image with a null detection AND a real detection that is fully classified
        by all pipeline algorithms should be skipped — it's fully processed.
        """
        from ami.ml.models.pipeline import filter_processed_images

        image = self.test_images[0]
        detector = self.algorithms["random-detector"]
        binary_classifier = self.algorithms["random-binary-classifier"]
        species_classifier = self.algorithms["random-species-classifier"]

        # Null detection from a prior empty run
        Detection.objects.create(
            source_image=image,
            detection_algorithm=detector,
            bbox=None,
        )
        # Real detection with classifications from all pipeline algorithms
        real_det = Detection.objects.create(
            source_image=image,
            detection_algorithm=detector,
            bbox=[0.1, 0.2, 0.3, 0.4],
        )
        taxon = Taxon.objects.create(name="Test Species Filtered")
        Classification.objects.create(
            detection=real_det,
            taxon=taxon,
            algorithm=binary_classifier,
            score=0.9,
            timestamp=datetime.datetime.now(),
        )
        Classification.objects.create(
            detection=real_det,
            taxon=taxon,
            algorithm=species_classifier,
            score=0.8,
            timestamp=datetime.datetime.now(),
        )

        result = list(filter_processed_images([image], self.pipeline))
        self.assertEqual(result, [], "Fully classified image with null detection should be skipped")

    def test_filter_processed_images_empty_input(self):
        """An empty iterable should yield nothing and run no per-image queries."""
        from ami.ml.models.pipeline import filter_processed_images

        with self.assertNumQueries(1):  # one query: pipeline.algorithms.all()
            result = list(filter_processed_images([], self.pipeline))
        self.assertEqual(result, [])

    def test_filter_processed_images_yields_all_when_pipeline_has_no_classifiers(self):
        """
        When a pipeline has no classifier algorithms registered, filter_processed_images
        must yield every image (matching the "Will reprocess all images" warning).
        Without the short-circuit, the empty `pipeline_classifier_ids` set makes
        `set().issubset(observed) == True` and every image with existing detections
        is silently skipped — directly contradicting the warning.
        """
        from ami.ml.models.pipeline import filter_processed_images

        detector_only_pipeline = Pipeline.objects.create(name="Detector Only Pipeline")
        detector_only_pipeline.algorithms.set([self.algorithms["random-detector"]])

        # Image with a real, fully-processed-looking detection from the detector.
        # Pre-short-circuit this would be skipped because the empty pipeline classifier
        # set is vacuously a subset of any observed-classifier set.
        image_with_detection = SourceImage.objects.create(path="no-classifier-with-det.jpg")
        Detection.objects.create(
            source_image=image_with_detection,
            detection_algorithm=self.algorithms["random-detector"],
            bbox=[0.1, 0.2, 0.3, 0.4],
        )
        image_unprocessed = SourceImage.objects.create(path="no-classifier-unprocessed.jpg")

        result = list(filter_processed_images([image_with_detection, image_unprocessed], detector_only_pipeline))
        self.assertEqual(result, [image_with_detection, image_unprocessed])

    def test_filter_processed_images_mixed_batch(self):
        """
        A mixed batch of images covering all five branches should yield only
        the ones that need processing, in input order.
        """
        from ami.ml.models.pipeline import filter_processed_images

        detector = self.algorithms["random-detector"]
        binary = self.algorithms["random-binary-classifier"]
        species = self.algorithms["random-species-classifier"]

        unprocessed = SourceImage.objects.create(path="unprocessed.jpg")
        null_only = SourceImage.objects.create(path="null_only.jpg")
        unclassified = SourceImage.objects.create(path="unclassified.jpg")
        fully_classified = SourceImage.objects.create(path="fully_classified.jpg")

        Detection.objects.create(source_image=null_only, detection_algorithm=detector, bbox=None)

        Detection.objects.create(source_image=unclassified, detection_algorithm=detector, bbox=[0.1, 0.2, 0.3, 0.4])

        real_det = Detection.objects.create(
            source_image=fully_classified, detection_algorithm=detector, bbox=[0.1, 0.2, 0.3, 0.4]
        )
        taxon = Taxon.objects.create(name="Test Mixed Batch Taxon")
        Classification.objects.create(
            detection=real_det, taxon=taxon, algorithm=binary, score=0.9, timestamp=datetime.datetime.now()
        )
        Classification.objects.create(
            detection=real_det, taxon=taxon, algorithm=species, score=0.8, timestamp=datetime.datetime.now()
        )

        images = [unprocessed, null_only, unclassified, fully_classified]
        result = list(filter_processed_images(images, self.pipeline))
        self.assertEqual(result, [unprocessed, unclassified])

    def test_filter_processed_images_query_count_is_bounded_per_batch(self):
        """
        With N images and batch_size=B, the query count should scale as
        O(N / B), not O(N). Locks in the bulk-query rewrite from issue #1321.

        Each batch issues at most:
          - 1 Detection bulk select
          - 1 Classification bulk select (only when real detections exist)
        Plus one initial pipeline.algorithms.all() that's shared across batches.
        """
        from ami.ml.models.pipeline import filter_processed_images

        detector = self.algorithms["random-detector"]
        binary = self.algorithms["random-binary-classifier"]
        species = self.algorithms["random-species-classifier"]
        taxon = Taxon.objects.create(name="Bounded Query Test Taxon")

        # 10 images. Batch 1: 5 fully-classified (triggers classification query).
        # Batch 2: 5 unprocessed (no detections, classification query skipped).
        images = [SourceImage.objects.create(path=f"bulk-{i}.jpg") for i in range(10)]
        for image in images[:5]:
            real_det = Detection.objects.create(
                source_image=image, detection_algorithm=detector, bbox=[0.1, 0.2, 0.3, 0.4]
            )
            Classification.objects.create(
                detection=real_det, taxon=taxon, algorithm=binary, score=0.9, timestamp=datetime.datetime.now()
            )
            Classification.objects.create(
                detection=real_det, taxon=taxon, algorithm=species, score=0.8, timestamp=datetime.datetime.now()
            )

        # Expected: 1 (pipeline) + 2 (detection × 2 batches) + 1 (classification, batch 1 only) = 4.
        with self.assertNumQueries(4):
            result = list(filter_processed_images(images, self.pipeline, batch_size=5))

        # First 5 fully classified → skipped. Last 5 fresh → yielded.
        self.assertEqual(result, images[5:])

    def test_filter_processed_images_emits_throttled_collect_progress(self):
        """
        When `job` and `total` are passed, filter_processed_images should call
        job.save(update_fields=["progress"]) at most once per
        COLLECT_PROGRESS_SAVE_INTERVAL_SECONDS of wall time, capped at
        COLLECT_PROGRESS_MAX_FRACTION. Keeps the reaper's "no forward progress"
        heuristic happy on multi-minute Collect stages without hot-saving the
        Job row on every chunk (issue #1321 follow-up).
        """
        from unittest.mock import patch

        from ami.jobs.models import Job, MLJob
        from ami.ml.models.pipeline import COLLECT_PROGRESS_MAX_FRACTION, filter_processed_images

        job = Job.objects.create(
            project=self.project,
            name="collect progress cadence test",
            pipeline=self.pipeline,
            job_type_key=MLJob.key,
        )
        # First save triggered MLJob.setup → "collect" stage exists.
        job.progress.get_stage("collect")

        images = [SourceImage.objects.create(path=f"cadence-{i}.jpg") for i in range(10)]

        # batch_size=3 over 10 images → 4 batches. Each monotonic() call
        # advances the clock by 3s. Expected sequence: init=0, batch1=3
        # (gap 3, no save), batch2=6 (gap 6, SAVE → last=6), batch3=9
        # (gap 3, no save), batch4=12 (gap 6, SAVE → last=12). Two saves.
        #
        # Counter-based stub (vs an iter/next sequence) means extra
        # monotonic() calls added to filter_processed_images later will
        # advance time faster and the assertion will fail with a clear
        # cadence mismatch, not StopIteration.
        clock = {"t": 0.0}

        def fake_monotonic():
            t = clock["t"]
            clock["t"] += 3.0
            return t

        with patch("ami.ml.models.pipeline.time.monotonic", side_effect=fake_monotonic):
            with patch.object(Job, "save", autospec=True) as mock_save:
                list(filter_processed_images(images, self.pipeline, batch_size=3, job=job, total=10))

        self.assertEqual(mock_save.call_count, 2, "Expected throttle to allow exactly 2 saves")
        for call in mock_save.call_args_list:
            self.assertEqual(
                call.kwargs.get("update_fields"),
                ["progress", "updated_at"],
                "Throttled saves must include `updated_at` so Django's auto_now fires "
                "and the reaper's stale-job heuristic sees forward motion.",
            )

        # Final emitted fraction comes from the second save (batch 4): processed=10,
        # total=10 → raw 1.0, capped at COLLECT_PROGRESS_MAX_FRACTION.
        collect_stage = job.progress.get_stage("collect")
        self.assertEqual(collect_stage.progress, COLLECT_PROGRESS_MAX_FRACTION)

    def test_filter_processed_images_skips_progress_emission_without_job(self):
        """
        Legacy callers that omit `job` (the only callers before this change)
        should see zero job.save() calls — the throttle block is fully gated
        on both `job` and `total` being passed.
        """
        from unittest.mock import patch

        from ami.jobs.models import Job
        from ami.ml.models.pipeline import filter_processed_images

        images = [SourceImage.objects.create(path=f"nojob-{i}.jpg") for i in range(5)]
        with patch.object(Job, "save", autospec=True) as mock_save:
            list(filter_processed_images(images, self.pipeline, batch_size=2))

        self.assertEqual(mock_save.call_count, 0)

    def test_null_detections_are_algorithm_specific(self):
        """
        Null detections from different pipelines/algorithms should not be shared.
        Each algorithm's null detection is tracked separately so that
        get_was_processed(algorithm_key=...) returns the correct per-algorithm status.
        """
        from ami.ml.models.pipeline import save_results

        image = self.test_images[0]

        # Pipeline 1 processes image, finds nothing
        results_1 = self.fake_pipeline_results([image], self.pipeline)
        results_1.detections = []
        save_results(results_1)

        # Create a second pipeline with a DIFFERENT detector algorithm
        detector_2, _ = Algorithm.objects.get_or_create(
            key="constant-detector",
            defaults={"name": "Constant Detector", "task_type": "detection"},
        )
        pipeline_2 = Pipeline.objects.create(name="Test Pipeline 2 Null Detect")
        pipeline_2.algorithms.set([detector_2])

        # Pipeline 2 processes the same image, also finds nothing
        results_2 = self.fake_pipeline_results([image], pipeline_2)
        results_2.detections = []
        save_results(results_2)

        # Both algorithms should independently mark the image as processed
        detector_1_key = self.algorithms["random-detector"].key
        self.assertTrue(image.get_was_processed(algorithm_key=detector_1_key))
        self.assertTrue(
            image.get_was_processed(algorithm_key="constant-detector"),
            "Pipeline 2's null detection should be created separately",
        )

        # Each pipeline must have its own null detection in the DB
        null_detections = image.detections.filter(bbox__isnull=True)
        self.assertEqual(null_detections.count(), 2, "Each pipeline should have its own null detection")

    def test_null_detection_deduplication_same_pipeline(self):
        """
        Running the same pipeline twice on the same image should not create
        duplicate null detections — the second run reuses the existing one.
        """
        from ami.ml.models.pipeline import save_results

        image = self.test_images[0]

        # Run pipeline twice, both with no detections
        results_1 = self.fake_pipeline_results([image], self.pipeline)
        results_1.detections = []
        save_results(results_1)

        results_2 = self.fake_pipeline_results([image], self.pipeline)
        results_2.detections = []
        save_results(results_2)

        # Should still be exactly one null detection
        null_detections = image.detections.filter(bbox__isnull=True)
        self.assertEqual(null_detections.count(), 1, "Same pipeline should not create duplicate null detections")

    def test_null_detection_does_not_create_phantom_occurrence(self):
        """
        Issue #1310: a null detection (empty-bbox sentinel marking "image processed,
        nothing found") must NOT spawn an Occurrence. Occurrences with no
        determination and no real detections leak to the API as ghost rows.
        """
        image = self.test_images[0]
        results = self.fake_pipeline_results([image], self.pipeline)
        results.detections = []  # pipeline found nothing

        save_results(results)

        null_dets = image.detections.filter(bbox__isnull=True)
        self.assertEqual(null_dets.count(), 1, "Null marker should still be created")
        self.assertIsNone(
            null_dets.first().occurrence,
            "Null detection must NOT be associated with an Occurrence",
        )
        # No phantom Occurrence in DB tied to this image at all
        phantom_occs = Occurrence.objects.filter(detections__source_image=image, determination__isnull=True)
        self.assertEqual(
            phantom_occs.count(),
            0,
            "No Occurrence with NULL determination should exist for an image that had no detections",
        )

    def test_captures_not_marked_processed_after_failure(self):
        """
        Issue #1310: null markers should only flag images as processed AFTER all
        downstream save steps (classifications, occurrences) succeed. If any
        downstream step raises, the image must remain unmarked so the next run
        re-processes it.

        Reproduces the field bug where 400 images ended up with null markers but
        no real detections — created when null-creation ran ahead of a later step
        that failed.
        """
        from unittest.mock import patch

        from ami.ml.models.pipeline import filter_processed_images

        # Mix: image_with_real has a detection in the response, image_without_real does not.
        # The without-real image is the one that would get a null marker.
        image_with_real, image_without_real = self.test_images
        results = self.fake_pipeline_results(self.test_images, self.pipeline)
        # Trim detections to only the first image so the second qualifies for null-marker creation
        results.detections = [d for d in results.detections if str(d.source_image_id) == str(image_with_real.pk)]

        # Inject failure in a step that runs AFTER detection bulk_create
        with patch(
            "ami.ml.models.pipeline.create_classifications",
            side_effect=RuntimeError("simulated classification failure"),
        ):
            with self.assertRaises(RuntimeError):
                save_results(results)

        # The image with no real detection must NOT have a null marker —
        # the run failed, so it should be re-tried.
        null_dets = image_without_real.detections.filter(bbox__isnull=True)
        self.assertEqual(
            null_dets.count(),
            0,
            "Image without real detections must not be marked processed when downstream step fails",
        )
        # filter_processed_images should still yield it for the next run
        retry_yield = list(filter_processed_images([image_without_real], self.pipeline))
        self.assertEqual(
            retry_yield,
            [image_without_real],
            "Image with failed run must be re-yielded for processing",
        )

    def test_null_marker_not_persisted_when_broker_dispatch_fails(self):
        """
        Issue #1310 (takeaway-review follow-up): null markers must be the FINAL
        write in save_results. Failures in any of the trailing steps —
        create_detection_images.delay (broker outage), update_calculated_fields_for_events
        (DB error), Deployment.update_calculated_fields (DB error) — must leave the
        image unmarked.

        This test patches the celery dispatch to raise, simulating a broker
        outage between the real-detection save and the null-marker save.
        """
        from unittest.mock import patch

        from ami.ml.models.pipeline import filter_processed_images

        image_with_real, image_without_real = self.test_images
        results = self.fake_pipeline_results(self.test_images, self.pipeline)
        results.detections = [d for d in results.detections if str(d.source_image_id) == str(image_with_real.pk)]

        with patch(
            "ami.ml.models.pipeline.create_detection_images.delay",
            side_effect=RuntimeError("simulated broker outage"),
        ):
            with self.assertRaises(RuntimeError):
                save_results(results)

        null_dets = image_without_real.detections.filter(bbox__isnull=True)
        self.assertEqual(
            null_dets.count(),
            0,
            "Null marker must not be persisted when create_detection_images.delay fails",
        )
        retry_yield = list(filter_processed_images([image_without_real], self.pipeline))
        self.assertEqual(
            retry_yield,
            [image_without_real],
            "Image with failed broker dispatch must be re-yielded for processing",
        )


class TestAlgorithmCategoryMaps(TestCase):
    def setUp(self):
        self.algorithm_responses = {
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.algorithms = {key: Algorithm.objects.get(key=key) for key in ALGORITHM_CHOICES.keys()}

    def test_create_algorithms_and_category_map(self):
        assert len(self.algorithms) > 0
        assert (
            Algorithm.objects.filter(
                key__in=self.algorithms.keys(),
            )
            .exclude(category_map=None)
            .count()
        ) > 0

    def test_algorithm_category_maps(self):
        for algorithm in Algorithm.objects.filter(
            key__in=self.algorithms.keys(),
        ).exclude(category_map=None):
            assert algorithm.category_map  # For type checker, not the test
            assert algorithm.category_map.labels
            assert algorithm.category_map.labels_hash
            assert algorithm.category_map.data

            # Ensure the full labels in the data match the simple, ordered list of labels
            sorted_data = sorted(algorithm.category_map.data, key=lambda x: x["index"])
            assert [category["label"] for category in sorted_data] == algorithm.category_map.labels

    def test_labels_hash_auto_generation(self):
        """Test that labels_hash is automatically generated when creating AlgorithmCategoryMap instances."""
        from ami.ml.models import AlgorithmCategoryMap

        # Test data
        test_data = [
            {"index": 0, "label": "coleoptera"},
            {"index": 1, "label": "diptera"},
            {"index": 2, "label": "lepidoptera"},
        ]
        test_labels = AlgorithmCategoryMap.labels_from_data(test_data)

        # Create instance using objects.create()
        category_map = AlgorithmCategoryMap.objects.create(labels=test_labels, data=test_data, version="test-v1")

        # Verify labels_hash was automatically generated
        self.assertIsNotNone(category_map.labels_hash)

        # Verify the hash matches what make_labels_hash would produce
        expected_hash = AlgorithmCategoryMap.make_labels_hash(test_labels)
        self.assertEqual(category_map.labels_hash, expected_hash)

        # Test that creating another instance with same labels produces same hash
        category_map2 = AlgorithmCategoryMap.objects.create(labels=test_labels, data=test_data, version="test-v2")

        self.assertEqual(category_map.labels_hash, category_map2.labels_hash)

    def test_labels_data_conversion_methods(self):
        from ami.ml.models import AlgorithmCategoryMap

        # Test data
        test_data = [
            {"index": 0, "label": "coleoptera"},
            {"index": 1, "label": "diptera"},
            {"index": 2, "label": "lepidoptera"},
        ]
        test_labels = AlgorithmCategoryMap.labels_from_data(test_data)

        # Convert labels to data and back
        converted_data = AlgorithmCategoryMap.data_from_labels(test_labels)
        converted_labels = AlgorithmCategoryMap.labels_from_data(converted_data)

        # Verify conversions are correct
        self.assertEqual(test_data, converted_data)
        self.assertEqual(test_labels, converted_labels)


class TestTaxaListFromCategoryMap(TestCase):
    """
    Algorithm.sync_taxa_list() writes a category map into a global TaxaList of every taxon
    the model can predict. Labels resolve by taxon name or search name; missing taxa are
    created with the map's rank, or reported; membership is reconciled exactly on every run,
    so a label that stops resolving drops its taxon from the list on the next sync.
    """

    def setUp(self):
        from ami.ml.models import AlgorithmCategoryMap

        self.by_name = Taxon.objects.create(name="Testmoth alpha", rank=TaxonRank.SPECIES.name)
        self.by_alias = Taxon.objects.create(
            name="Testmoth beta", rank=TaxonRank.SPECIES.name, search_names=["Testmoth beta-old"]
        )
        data = [
            {"index": 0, "label": "Testmoth alpha", "taxon_rank": "SPECIES"},
            {"index": 1, "label": "Testmoth beta-old", "taxon_rank": "SPECIES"},
            {"index": 2, "label": "Testgenus", "taxon_rank": "GENUS"},
        ]
        self.category_map = AlgorithmCategoryMap.objects.create(
            data=data, labels=AlgorithmCategoryMap.labels_from_data(data), version="test"
        )
        self.algorithm = Algorithm.objects.create(
            name="Test butterflies", key="test-butterflies", category_map=self.category_map
        )

    def test_labels_resolve_by_name_or_search_name(self):
        resolved, unresolved = self.category_map.resolve_taxa()

        self.assertEqual(resolved, {"Testmoth alpha": self.by_name, "Testmoth beta-old": self.by_alias})
        self.assertEqual(unresolved, ["Testgenus"])

    def test_sync_creates_a_list_and_links_the_algorithm_to_it(self):
        result = self.algorithm.sync_taxa_list()

        self.assertTrue(result.created_list)
        self.assertEqual(
            (result.labels, result.matched, result.created_taxa, result.removed, result.unresolved),
            (3, 2, 1, 0, []),
        )
        self.assertEqual(result.taxa_list.name, "Category map of Test butterflies")
        self.assertEqual(result.taxa_list.projects.count(), 0)
        self.algorithm.refresh_from_db()
        self.assertEqual(self.algorithm.taxa_list_id, result.taxa_list.pk)
        created = Taxon.objects.get(name="Testgenus")
        self.assertEqual(created.rank, TaxonRank.GENUS.name)
        self.assertEqual(set(result.taxa_list.taxa.all()), {self.by_name, self.by_alias, created})

    def test_missing_taxa_can_be_reported_instead_of_created(self):
        result = self.algorithm.sync_taxa_list(create_missing_taxa=False)

        self.assertEqual((result.matched, result.created_taxa, result.unresolved), (2, 0, ["Testgenus"]))
        self.assertFalse(Taxon.objects.filter(name="Testgenus").exists())
        self.assertEqual(set(result.taxa_list.taxa.all()), {self.by_name, self.by_alias})

    def test_second_run_reuses_the_list_and_changes_nothing(self):
        first = self.algorithm.sync_taxa_list()
        second = self.algorithm.sync_taxa_list()

        self.assertEqual(second.taxa_list.pk, first.taxa_list.pk)
        self.assertFalse(second.created_list)
        self.assertEqual((second.matched, second.created_taxa, second.removed), (3, 0, 0))
        self.assertEqual(second.taxa_list.taxa.count(), 3)

    def test_membership_drops_a_taxon_whose_label_stops_resolving(self):
        first = self.algorithm.sync_taxa_list()
        self.assertEqual(first.taxa_list.taxa.count(), 3)

        # The alias is what made "Testmoth beta-old" resolve; removing it, without
        # touching the taxon's name, isolates a label that stops resolving from a
        # taxon that stops existing (a separate, already-covered case).
        self.by_alias.search_names = []
        self.by_alias.save()

        second = self.algorithm.sync_taxa_list(create_missing_taxa=False)

        self.assertEqual((second.matched, second.created_taxa, second.removed), (2, 0, 1))
        self.assertEqual(second.unresolved, ["Testmoth beta-old"])
        self.assertEqual(second.taxa_list.pk, first.taxa_list.pk)
        self.assertFalse(second.taxa_list.taxa.filter(pk=self.by_alias.pk).exists())

    def test_two_algorithms_sharing_a_category_map_share_one_list(self):
        sibling = Algorithm.objects.create(
            name="Test butterflies v2", key="test-butterflies-v2", category_map=self.category_map
        )

        first = self.algorithm.sync_taxa_list()
        second = sibling.sync_taxa_list()

        self.assertEqual(second.taxa_list.pk, first.taxa_list.pk)
        self.assertFalse(second.created_list)
        sibling.refresh_from_db()
        self.algorithm.refresh_from_db()
        self.assertEqual(sibling.taxa_list_id, self.algorithm.taxa_list_id)

    def test_algorithm_without_a_category_map_does_nothing(self):
        bare = Algorithm.objects.create(name="Bare", key="bare")

        result = bare.sync_taxa_list()

        self.assertIsNone(result.taxa_list)
        self.assertEqual((result.labels, result.matched, result.created_taxa, result.removed), (0, 0, 0, 0))

    def test_category_map_with_no_labels_does_nothing(self):
        from ami.ml.models import AlgorithmCategoryMap

        empty_map = AlgorithmCategoryMap.objects.create(data=[], labels=[], version="empty")
        empty_algorithm = Algorithm.objects.create(name="Empty Map Algo", key="empty-map-algo", category_map=empty_map)

        result = empty_algorithm.sync_taxa_list()

        self.assertIsNone(result.taxa_list)

    def test_management_command_dry_run_writes_nothing(self):
        from io import StringIO

        from django.core.management import call_command

        from ami.main.models import TaxaList

        out = StringIO()
        call_command(
            "create_taxa_lists_from_category_maps", "--algorithm", "test-butterflies", "--dry-run", stdout=out
        )

        self.assertIn("3 labels, 2 matched existing taxa, 1 taxa created", out.getvalue())
        self.assertFalse(TaxaList.objects.filter(name="Category map of Test butterflies").exists())
        self.assertFalse(Taxon.objects.filter(name="Testgenus").exists())

        call_command("create_taxa_lists_from_category_maps", "--algorithm", "test-butterflies", stdout=out)
        taxa_list = TaxaList.objects.get(name="Category map of Test butterflies")
        self.assertEqual(taxa_list.taxa.count(), 3)
        self.algorithm.refresh_from_db()
        self.assertEqual(self.algorithm.taxa_list_id, taxa_list.pk)


class TestAlgorithmTaxaListVisibility(TestCase):
    """
    A managed list's visibility follows the processing services offering the algorithm:
    public if any of them is public, else scoped to the union of their projects, else
    visible to superusers only (no service offers the algorithm at all).
    """

    def setUp(self):
        from ami.ml.models import AlgorithmCategoryMap

        self.taxon = Taxon.objects.create(name="Visibility Testmoth", rank=TaxonRank.SPECIES.name)
        data = [{"index": 0, "label": "Visibility Testmoth", "taxon_rank": "SPECIES"}]
        self.category_map = AlgorithmCategoryMap.objects.create(
            data=data, labels=AlgorithmCategoryMap.labels_from_data(data), version="test"
        )
        self.algorithm = Algorithm.objects.create(
            name="Visibility Test Algo", key="visibility-test-algo", category_map=self.category_map
        )
        self.pipeline = Pipeline.objects.create(name="Visibility Test Pipeline")
        self.pipeline.algorithms.add(self.algorithm)

    def test_no_offering_service_gives_a_superuser_only_list(self):
        result = self.algorithm.sync_taxa_list()

        self.assertFalse(result.taxa_list.is_public)
        self.assertEqual(result.taxa_list.projects.count(), 0)

    def test_a_public_offering_service_makes_the_list_public(self):
        service = ProcessingService.objects.create(name="Public PS", endpoint_url=None, is_public=True)
        service.pipelines.add(self.pipeline)

        result = self.algorithm.sync_taxa_list()

        self.assertTrue(result.taxa_list.is_public)
        self.assertEqual(result.taxa_list.projects.count(), 0)

    def test_project_scoped_offering_services_scope_the_list_to_their_projects(self):
        project_a = Project.objects.create(name="Visibility Project A")
        project_b = Project.objects.create(name="Visibility Project B")
        service_a = ProcessingService.objects.create(name="Service A", endpoint_url=None)
        service_a.projects.add(project_a)
        service_a.pipelines.add(self.pipeline)
        # A service offering a different pipeline must not widen the list's scope.
        other_pipeline = Pipeline.objects.create(name="Unrelated Pipeline")
        service_b = ProcessingService.objects.create(name="Service B", endpoint_url=None)
        service_b.projects.add(project_b)
        service_b.pipelines.add(other_pipeline)

        result = self.algorithm.sync_taxa_list()

        self.assertFalse(result.taxa_list.is_public)
        self.assertEqual(set(result.taxa_list.projects.all()), {project_a})

    def test_an_offering_service_with_no_projects_does_not_break_scoping(self):
        """A service can offer a pipeline with no projects attached (``projects`` is
        blank=True); it must not contribute a null project to the list's scope."""
        project_a = Project.objects.create(name="Visibility Project A")
        service_a = ProcessingService.objects.create(name="Service A", endpoint_url=None)
        service_a.projects.add(project_a)
        service_a.pipelines.add(self.pipeline)
        orphan_service = ProcessingService.objects.create(name="Orphan Service", endpoint_url=None)
        orphan_service.pipelines.add(self.pipeline)

        result = self.algorithm.sync_taxa_list()

        self.assertFalse(result.taxa_list.is_public)
        self.assertEqual(set(result.taxa_list.projects.all()), {project_a})


@override_settings(CACHALOT_ENABLED=False)
class TestSyncTaxaListQueryCost(TestCase):
    """
    sync_taxa_list() resolves and reconciles membership with a fixed number of queries:
    every step (resolve, sibling lookup, membership diff, visibility) issues one query
    per algorithm run regardless of how many labels the category map holds, using
    ``__in``/bulk operations rather than a query per label.
    """

    def _build_algorithm(self, key: str, label_count: int) -> Algorithm:
        from ami.ml.models import AlgorithmCategoryMap

        data = []
        for i in range(label_count):
            name = f"{key} species {i}"
            Taxon.objects.create(name=name, rank=TaxonRank.SPECIES.name)
            data.append({"index": i, "label": name, "taxon_rank": "SPECIES"})
        category_map = AlgorithmCategoryMap.objects.create(
            data=data, labels=AlgorithmCategoryMap.labels_from_data(data), version=key
        )
        return Algorithm.objects.create(name=key, key=key, category_map=category_map)

    def test_query_count_is_the_same_for_5_and_50_labels(self):
        small = self._build_algorithm("qc-small", 5)
        large = self._build_algorithm("qc-large", 50)

        with CaptureQueriesContext(connection) as small_ctx:
            small.sync_taxa_list()
        with CaptureQueriesContext(connection) as large_ctx:
            large.sync_taxa_list()

        self.assertEqual(len(small_ctx.captured_queries), len(large_ctx.captured_queries))


class TestAlgorithmSerializerTaxaList(APITestCase):
    """The algorithm API exposes the taxa list an algorithm is synced to, or null before
    any sync has happened. See Algorithm.sync_taxa_list()."""

    def setUp(self):
        from ami.ml.models import AlgorithmCategoryMap

        self.user = User.objects.create_user(email="algo-taxalist-user@example.com", password="testpass")
        taxon = Taxon.objects.create(name="Serializer Test Taxon", rank=TaxonRank.SPECIES.name)
        data = [{"index": 0, "label": taxon.name, "taxon_rank": "SPECIES"}]
        self.category_map = AlgorithmCategoryMap.objects.create(
            data=data, labels=AlgorithmCategoryMap.labels_from_data(data), version="serializer-test"
        )
        self.algorithm = Algorithm.objects.create(
            name="Serializer Test Algo", key="serializer-test-algo", category_map=self.category_map
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _detail_url(self):
        return f"/api/v2/ml/algorithms/{self.algorithm.pk}/"

    def test_taxa_list_is_null_before_a_sync(self):
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()["taxa_list"])

    def test_taxa_list_is_id_and_name_after_a_sync(self):
        result = self.algorithm.sync_taxa_list()

        response = self.client.get(self._detail_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["taxa_list"], {"id": result.taxa_list.pk, "name": result.taxa_list.name})


@override_settings(CACHALOT_ENABLED=False)
class AlgorithmQueryCountTestCase(APITestCase):
    """Audit AlgorithmViewSet.list for N+1 from the nested taxa_list field, across a
    fixture mixing algorithms with and without a synced list."""

    def setUp(self):
        from ami.ml.models import AlgorithmCategoryMap

        self.user = User.objects.create_user(email="algo-qc-user@example.com", password="testpass")
        for i in range(3):
            Algorithm.objects.create(name=f"QC Bare Algo {i}", key=f"qc-bare-algo-{i}")
        for i in range(2):
            taxon = Taxon.objects.create(name=f"QC Linked Taxon {i}", rank=TaxonRank.SPECIES.name)
            data = [{"index": 0, "label": taxon.name, "taxon_rank": "SPECIES"}]
            category_map = AlgorithmCategoryMap.objects.create(
                data=data, labels=AlgorithmCategoryMap.labels_from_data(data), version=f"qc-linked-{i}"
            )
            algorithm = Algorithm.objects.create(
                name=f"QC Linked Algo {i}", key=f"qc-linked-algo-{i}", category_map=category_map
            )
            algorithm.sync_taxa_list()

        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_query_count(self):
        from cachalot.api import cachalot_disabled

        # Scoped to this fixture's own rows with ?search=, so pre-existing demo
        # algorithms created by other signals don't skew the row/query count.
        with cachalot_disabled(), CaptureQueriesContext(connection) as ctx:
            response = self.client.get("/api/v2/ml/algorithms/", {"search": "QC "})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["results"]), 5)
        self.assertEqual(len(ctx.captured_queries), 4)


class TestPostProcessingTasks(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Project, taxa, images, events, and the collection are read-only from the
        # tests' point of view — build them once per class. Detections (and the
        # task runs that mutate them) happen per-test inside each test's
        # rolled-back transaction.
        cls.project, cls.deployment = setup_test_project()
        create_taxa(project=cls.project)
        cls._create_images_with_dimensions(deployment=cls.deployment)
        group_images_into_events(deployment=cls.deployment)

        # Create a simple SourceImageCollection for testing
        cls.collection = SourceImageCollection.objects.create(
            name="Test PostProcessing Collection",
            project=cls.project,
            method="manual",
            kwargs={"image_ids": list(cls.deployment.captures.values_list("pk", flat=True))},
        )
        cls.collection.populate_sample()

    @classmethod
    def _create_images_with_dimensions(
        cls,
        deployment,
        num_images: int = 5,
        width: int = 640,
        height: int = 480,
        update_deployment: bool = True,
    ):
        """
        Create SourceImages for a deployment with specified width and height.
        """

        created = []
        base_time = datetime.datetime.now(datetime.timezone.utc)

        for i in range(num_images):
            random_prefix = uuid.uuid4().hex[:8]
            path = pathlib.Path("test") / f"{random_prefix}_{i}.jpg"

            image = SourceImage.objects.create(
                deployment=deployment,
                project=deployment.project,
                timestamp=base_time + datetime.timedelta(minutes=i * 5),
                path=path,
                width=width,
                height=height,
            )
            created.append(image)

        if update_deployment:
            deployment.save(update_calculated_fields=True, regroup_async=False)

    def test_small_size_filter_assigns_not_identifiable(self):
        """
        Test that SmallSizeFilterTask correctly assigns 'Not identifiable'
        to detections below the configured minimum size.
        """
        # Create small detections on the collection images
        for image in self.collection.images.all():
            Detection.objects.create(
                source_image=image,
                bbox=[0, 0, 10, 10],  # small detection
                created_at=datetime.datetime.now(datetime.timezone.utc),
            ).associate_new_occurrence()

        # Prepare the task configuration
        task = SmallSizeFilterTask(
            source_image_collection_id=self.collection.pk,
            size_threshold=0.01,
        )

        task.run()

        # Verify that all small detections are now classified as "Not identifiable"
        not_identifiable_taxon = Taxon.objects.get(name="Not identifiable")
        detections = Detection.objects.filter(source_image__in=self.collection.images.all())

        for det in detections:
            latest_classification = Classification.objects.filter(detection=det).order_by("-created_at").first()
            self.assertIsNotNone(latest_classification, "Each detection should have a classification.")
            self.assertEqual(
                latest_classification.taxon,
                not_identifiable_taxon,
                f"Detection {det.pk} should be classified as 'Not identifiable'",
            )
            occurrence = det.occurrence
            self.assertIsNotNone(occurrence, f"Detection {det.pk} should belong to an occurrence.")
            occurrence.refresh_from_db()
            self.assertEqual(
                occurrence.determination,
                not_identifiable_taxon,
                f"Occurrence {occurrence.pk} should have its determination set to 'Not identifiable'.",
            )

    def test_occurrence_scope_only_touches_that_occurrence(self):
        """Per-occurrence scope: running with ``occurrence_id`` flags only that
        occurrence's detections and leaves sibling occurrences untouched."""
        detections = []
        for image in self.collection.images.all():
            det = Detection.objects.create(
                source_image=image,
                bbox=[0, 0, 10, 10],  # small
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            det.associate_new_occurrence()
            detections.append(det)
        self.assertGreaterEqual(len(detections), 2)

        target = detections[0]
        SmallSizeFilterTask(occurrence_id=target.occurrence_id, size_threshold=0.01).run()

        not_identifiable_taxon = Taxon.objects.get(name="Not identifiable")
        self.assertEqual(
            Classification.objects.filter(detection=target, taxon=not_identifiable_taxon).count(),
            1,
            "The scoped occurrence's detection should be flagged.",
        )
        for other in detections[1:]:
            self.assertFalse(
                Classification.objects.filter(detection=other, taxon=not_identifiable_taxon).exists(),
                f"Detection {other.pk} outside the scoped occurrence should be untouched.",
            )

    def test_run_reports_stage_metrics_on_job(self):
        """The task surfaces ``detections_checked`` / ``detections_flagged`` /
        ``occurrences_updated`` as stage params on its Job so an operator can see
        what a run examined and changed without reading the log."""
        from ami.jobs.models import Job

        for image in self.collection.images.all():
            Detection.objects.create(
                source_image=image,
                bbox=[0, 0, 10, 10],  # small → flagged
                created_at=datetime.datetime.now(datetime.timezone.utc),
            ).associate_new_occurrence()
        total = Detection.objects.filter(source_image__in=self.collection.images.all()).count()
        self.assertGreater(total, 0)

        job = Job.objects.create(
            project=self.project,
            name="stage metrics test",
            job_type_key="post_processing",
            params={
                "task": "small_size_filter",
                "config": {"source_image_collection_id": self.collection.pk, "size_threshold": 0.01},
            },
        )
        job.progress.add_stage("Post Processing", key="post_processing")
        job.save()

        SmallSizeFilterTask(
            job=job,
            source_image_collection_id=self.collection.pk,
            size_threshold=0.01,
        ).run()

        job.refresh_from_db()
        params = {p.name: p.value for p in job.progress.get_stage("post_processing").params}
        self.assertEqual(params.get("detections_checked"), total)
        self.assertEqual(params.get("detections_flagged"), total)  # every detection is small
        # Each detection has its own occurrence here, so the deduped occurrence
        # count equals the detection count.
        self.assertEqual(params.get("occurrences_updated"), total)

    def test_progress_save_bumps_updated_at_for_reaper(self):
        """A progress heartbeat bumps ``Job.updated_at`` so the stale-job reaper
        leaves an actively-running post-processing job alone.

        ``check_stale_jobs`` revokes running jobs whose ``updated_at`` is older
        than ``STALLED_JOBS_MAX_MINUTES``. The progress save narrows to
        ``update_fields``, and Django does not auto-add ``auto_now`` fields to
        that list, so ``update_progress`` / ``report_stage_metrics`` must include
        ``updated_at`` explicitly. Without it a long run looks frozen and is
        reaped mid-flight even while streaming progress. This pins that both save
        paths move ``updated_at`` forward.
        """
        from ami.jobs.models import Job

        job = Job.objects.create(
            project=self.project,
            name="reaper heartbeat test",
            job_type_key="post_processing",
            params={
                "task": "small_size_filter",
                "config": {"source_image_collection_id": self.collection.pk, "size_threshold": 0.01},
            },
        )
        job.progress.add_stage("Post Processing", key="post_processing")
        job.save()

        task = SmallSizeFilterTask(
            job=job,
            source_image_collection_id=self.collection.pk,
            size_threshold=0.01,
        )

        # Freeze a baseline older than the reaper cutoff, then confirm each
        # heartbeat path drags updated_at back to "now". USE_TZ is False, so
        # updated_at is naive local time — mirror check_stale_jobs' own
        # naive datetime.now() comparison.
        stale = datetime.datetime.now() - datetime.timedelta(minutes=Job.STALLED_JOBS_MAX_MINUTES + 5)

        Job.objects.filter(pk=job.pk).update(updated_at=stale)
        task.update_progress(0.5)
        job.refresh_from_db()
        self.assertGreater(job.updated_at, stale, "update_progress must bump updated_at")

        Job.objects.filter(pk=job.pk).update(updated_at=stale)
        task.report_stage_metrics({"classifications_checked": 1})
        job.refresh_from_db()
        self.assertGreater(job.updated_at, stale, "report_stage_metrics must bump updated_at")

    def test_post_processing_stage_is_started_before_the_task_runs(self):
        """The stage reads as running from the moment the job starts.

        A task's first progress report can be minutes into a large run, and a stage
        left at CREATED renders as "Waiting to start" until then. See #1376.
        """
        from unittest.mock import patch

        from ami.jobs.models import Job, JobState, PostProcessingJob

        job = Job.objects.create(
            project=self.project,
            name="stage status test",
            job_type_key="post_processing",
            params={
                "task": "small_size_filter",
                "config": {"source_image_collection_id": self.collection.pk, "size_threshold": 0.01},
            },
        )

        observed = {}

        def _capture(self_task):
            stage = self_task.job.progress.get_stage("post_processing")
            observed["status"] = stage.status
            observed["label"] = stage.status_label

        with patch.object(SmallSizeFilterTask, "run", _capture):
            PostProcessingJob.run(job)

        self.assertEqual(observed["status"], JobState.STARTED)
        self.assertEqual(observed["label"], "0% complete")

    def test_occurrences_updated_counts_only_changed_determinations(self):
        """``occurrences_updated`` counts occurrences whose determination actually
        changed, not every occurrence the filter re-saved.

        An occurrence already pinned to a human identification keeps that
        determination when its detection is flagged "Not identifiable", so it must
        not inflate the metric. Only the un-identified occurrence, whose
        determination flips, is counted.
        """
        from ami.jobs.models import Job

        images = list(self.collection.images.all())
        self.assertGreaterEqual(len(images), 2)

        # Occurrence A: small detection, but a human identification pins the
        # determination — flagging the detection does not change it.
        human_taxon = Taxon.objects.create(name="Human-pinned species", rank=TaxonRank.SPECIES)
        identifier = User.objects.create_user(email="identifier@insectai.org")  # type: ignore[attr-defined]
        det_with_id = Detection.objects.create(
            source_image=images[0],
            bbox=[0, 0, 10, 10],
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        det_with_id.associate_new_occurrence()
        Identification.objects.create(user=identifier, occurrence=det_with_id.occurrence, taxon=human_taxon)

        # Occurrence B: small detection, no identification — its determination
        # flips to "Not identifiable" and is the only real change.
        det_plain = Detection.objects.create(
            source_image=images[1],
            bbox=[0, 0, 10, 10],
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        det_plain.associate_new_occurrence()

        job = Job.objects.create(
            project=self.project,
            name="changed-determination metric test",
            job_type_key="post_processing",
            params={
                "task": "small_size_filter",
                "config": {"source_image_collection_id": self.collection.pk, "size_threshold": 0.01},
            },
        )
        job.progress.add_stage("Post Processing", key="post_processing")
        job.save()

        SmallSizeFilterTask(
            job=job,
            source_image_collection_id=self.collection.pk,
            size_threshold=0.01,
        ).run()

        job.refresh_from_db()
        params = {p.name: p.value for p in job.progress.get_stage("post_processing").params}
        # Both detections are flagged small, but only the un-identified
        # occurrence's determination changes, so only it is counted.
        self.assertEqual(params.get("detections_flagged"), 2)
        self.assertEqual(params.get("occurrences_updated"), 1)


class TestTaskStateManager(TestCase):
    """Test TaskStateManager for job progress tracking."""

    def setUp(self):
        """Set up test fixtures."""
        from django.core.cache import cache

        from ami.ml.orchestration.async_job_state import AsyncJobStateManager

        cache.clear()
        self.job_id = 123
        self.manager = AsyncJobStateManager(self.job_id)
        self.image_ids = ["img1", "img2", "img3", "img4", "img5"]

    def _init_and_verify(self, image_ids):
        """Helper to initialize job and verify initial state."""
        self.manager.initialize_job(image_ids)
        progress = self.manager.get_progress("process")
        assert progress is not None
        self.assertEqual(progress.total, len(image_ids))
        self.assertEqual(progress.remaining, len(image_ids))
        self.assertEqual(progress.processed, 0)
        self.assertEqual(progress.percentage, 0.0)
        self.assertEqual(progress.failed, 0)
        return progress

    def test_initialize_job(self):
        """Test job initialization sets up tracking for all stages."""
        self._init_and_verify(self.image_ids)

        # Verify both stages are initialized
        for stage in self.manager.STAGES:
            progress = self.manager.get_progress(stage)
            assert progress is not None
            self.assertEqual(progress.total, len(self.image_ids))
            self.assertEqual(progress.failed, 0)

    def test_progress_tracking(self):
        """Test progress updates correctly as images are processed."""
        self._init_and_verify(self.image_ids)

        # Process 2 images
        progress = self.manager.update_state({"img1", "img2"}, "process")
        assert progress is not None
        self.assertEqual(progress.remaining, 3)
        self.assertEqual(progress.processed, 2)
        self.assertEqual(progress.percentage, 0.4)

        # Process 2 more images
        progress = self.manager.update_state({"img3", "img4"}, "process")
        assert progress is not None
        self.assertEqual(progress.remaining, 1)
        self.assertEqual(progress.processed, 4)
        self.assertEqual(progress.percentage, 0.8)

        # Process last image
        progress = self.manager.update_state({"img5"}, "process")
        assert progress is not None
        self.assertEqual(progress.remaining, 0)
        self.assertEqual(progress.processed, 5)
        self.assertEqual(progress.percentage, 1.0)

    def test_update_state_concurrent(self):
        """Test that concurrent workers update state correctly without data races."""
        self._init_and_verify(self.image_ids)

        # Three workers process disjoint image sets truly concurrently
        errors: list[BaseException] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(self.manager.update_state, {"img1", "img2"}, "process"),
                executor.submit(self.manager.update_state, {"img3"}, "process"),
                executor.submit(self.manager.update_state, {"img4", "img5"}, "process"),
            ]
            _errors = [f.exception() for f in concurrent.futures.as_completed(futures)]
            errors = [e for e in _errors if e is not None]

        self.assertEqual(errors, [], f"Concurrent workers raised exceptions: {errors}")

        # Final state reflects all concurrent updates
        final = self.manager.get_progress("process")
        assert final is not None
        self.assertEqual(final.processed, 5)
        self.assertEqual(final.remaining, 0)

        # SREM is idempotent: retrying already-processed images doesn't change counts
        progress_retry = self.manager.update_state({"img1", "img2"}, "process")
        assert progress_retry is not None
        self.assertEqual(progress_retry.processed, 5)

    def test_stages_independent(self):
        """Test that different stages track progress independently."""
        self._init_and_verify(self.image_ids)

        # Update process stage
        self.manager.update_state({"img1", "img2"}, "process")
        progress_process = self.manager.get_progress("process")
        assert progress_process is not None
        self.assertEqual(progress_process.remaining, 3)

        # Results stage should still have all images pending
        progress_results = self.manager.get_progress("results")
        assert progress_results is not None
        self.assertEqual(progress_results.remaining, 5)

    def test_empty_job(self):
        """Test handling of job with no images."""
        self.manager.initialize_job([])
        progress = self.manager.get_progress("process")
        assert progress is not None
        self.assertEqual(progress.total, 0)
        self.assertEqual(progress.percentage, 1.0)  # Empty job is 100% complete

    def test_cleanup(self):
        """Test cleanup removes all tracking keys."""
        self._init_and_verify(self.image_ids)

        # Verify keys exist
        progress = self.manager.get_progress("process")
        self.assertIsNotNone(progress)

        # Cleanup
        self.manager.cleanup()

        # Verify keys are gone
        progress = self.manager.get_progress("process")
        self.assertIsNone(progress)

    def test_failed_image_tracking(self):
        """Test basic failed image tracking with no double-counting on retries."""
        self._init_and_verify(self.image_ids)

        # Mark 2 images as failed in process stage
        progress = self.manager.update_state({"img1", "img2"}, "process", failed_image_ids={"img1", "img2"})
        assert progress is not None
        self.assertEqual(progress.failed, 2)

        # Retry same 2 images (fail again) - SADD is idempotent, no double-counting
        progress = self.manager.update_state(set(), "process", failed_image_ids={"img1", "img2"})
        assert progress is not None
        self.assertEqual(progress.failed, 2)

        # Fail a different image
        progress = self.manager.update_state(set(), "process", failed_image_ids={"img3"})
        assert progress is not None
        self.assertEqual(progress.failed, 3)

    def test_failed_and_processed_mixed(self):
        """Test mixed successful and failed processing in same batch."""
        self._init_and_verify(self.image_ids)

        # Process 2 successfully, 2 fail, 1 remains pending
        progress = self.manager.update_state(
            {"img1", "img2", "img3", "img4"}, "process", failed_image_ids={"img3", "img4"}
        )
        assert progress is not None
        self.assertEqual(progress.processed, 4)
        self.assertEqual(progress.failed, 2)
        self.assertEqual(progress.remaining, 1)
        self.assertEqual(progress.percentage, 0.8)

    def test_cleanup_removes_failed_set(self):
        """Test that cleanup removes failed image set."""
        self._init_and_verify(self.image_ids)

        # Add failed images and verify they're tracked
        progress = self.manager.update_state({"img1", "img2"}, "process", failed_image_ids={"img1", "img2"})
        assert progress is not None
        self.assertEqual(progress.failed, 2)

        # Cleanup
        self.manager.cleanup()

        # Verify all state is gone (get_progress returns None when total_key is deleted)
        progress = self.manager.get_progress("process")
        self.assertIsNone(progress)

    def test_update_state_raises_on_redis_error(self):
        """
        A transient Redis failure during update_state must propagate, not be
        swallowed as None. The None return is reserved for the genuine
        "state actually gone" case (see test below). Conflating the two is
        the #1219 bug that escalated transient connection resets into fatal
        job FAILUREs.
        """
        from unittest.mock import MagicMock, patch

        from redis.exceptions import RedisError

        self._init_and_verify(self.image_ids)

        # Replace the pipeline context manager with one whose execute() raises.
        # Everything upstream of execute() is safely called (srem/sadd/scard/get
        # on a pipeline only queue commands; they don't hit the network until
        # execute runs), so we only need to blow up at the execute boundary.
        pipe = MagicMock()
        pipe.execute.side_effect = RedisError("Connection reset by peer")
        fake_redis = MagicMock()
        fake_redis.pipeline.return_value.__enter__.return_value = pipe

        with patch.object(self.manager, "_get_redis", return_value=fake_redis):
            with self.assertRaises(RedisError):
                self.manager.update_state({"img1", "img2"}, "process")

    def test_update_state_returns_none_when_state_genuinely_missing(self):
        """
        When the job's total-images key is actually missing from Redis (job
        was never initialized, cleaned up, or TTL expired), update_state
        returns None. This is the only case that should trigger the
        terminal "state missing" failure path in the caller.
        """
        # Do NOT call initialize_job — the total key doesn't exist.
        progress = self.manager.update_state({"img1", "img2"}, "process")
        self.assertIsNone(progress)


class TestSaveResultsRefreshesDeploymentCounts(TestCase):
    """save_results must refresh Deployment cached counts, not just Event counts.

    Reproduces the "Station counts for occurrences and taxa are not always
    getting updated" report: prior to the fix, save_results refreshed
    update_calculated_fields_for_events but never the parent Deployment, so
    deployment.occurrences_count / taxa_count stayed at the pre-job value
    until something else (a manual deployment.save) ran.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Refresh Counts Project")
        self.deployment = Deployment.objects.create(name="d1", project=self.project)
        event_time = datetime.datetime(2026, 4, 16, 22, 0, 0)
        self.event = Event.objects.create(
            project=self.project,
            deployment=self.deployment,
            group_by="2026-04-16",
            start=event_time,
            end=event_time,
        )
        self.image = SourceImage.objects.create(
            deployment=self.deployment,
            project=self.project,
            event=self.event,
            timestamp=event_time,
            path="refresh_counts_test.jpg",
        )
        self.collection = SourceImageCollection.objects.create(project=self.project, name="c")
        self.collection.images.add(self.image)

        self.pipeline = Pipeline.objects.create(name="Refresh Counts Pipeline (Random)")
        self.algorithms = {
            key: get_or_create_algorithm_and_category_map(val) for key, val in ALGORITHM_CHOICES.items()
        }
        self.pipeline.algorithms.set(
            [
                self.algorithms["random-detector"],
                self.algorithms["random-binary-classifier"],
                self.algorithms["random-species-classifier"],
            ]
        )

        self.deployment.update_calculated_fields(save=True)
        self.deployment.refresh_from_db()
        self.assertEqual(self.deployment.occurrences_count, 0)
        self.assertEqual(self.deployment.taxa_count, 0)

    def _fake_results(self):
        detector = ALGORITHM_CHOICES["random-detector"]
        binary_classifier = ALGORITHM_CHOICES["random-binary-classifier"]
        species_classifier = ALGORITHM_CHOICES["random-species-classifier"]
        assert binary_classifier.category_map and species_classifier.category_map

        detection = DetectionResponse(
            source_image_id=self.image.pk,
            bbox=BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0),
            inference_time=0.1,
            algorithm=AlgorithmReference(name=detector.name, key=detector.key),
            timestamp=self.image.timestamp,
            classifications=[
                ClassificationResponse(
                    classification=binary_classifier.category_map.labels[0],
                    labels=binary_classifier.category_map.labels,
                    scores=[0.95],
                    algorithm=AlgorithmReference(name=binary_classifier.name, key=binary_classifier.key),
                    timestamp=self.image.timestamp,
                    terminal=False,
                ),
                ClassificationResponse(
                    classification=species_classifier.category_map.labels[0],
                    labels=species_classifier.category_map.labels,
                    scores=[0.85],
                    algorithm=AlgorithmReference(name=species_classifier.name, key=species_classifier.key),
                    timestamp=self.image.timestamp,
                    terminal=True,
                ),
            ],
        )
        return PipelineResultsResponse(
            pipeline=self.pipeline.slug,
            algorithms={
                detector.key: detector,
                binary_classifier.key: binary_classifier,
                species_classifier.key: species_classifier,
            },
            total_time=0.01,
            source_images=[SourceImageResponse(id=self.image.pk, url=self.image.path)],
            detections=[detection],
        )

    def test_deployment_counts_refresh_after_save_results(self):
        save_results(self._fake_results())

        self.deployment.refresh_from_db()
        self.assertGreater(
            self.deployment.occurrences_count,
            0,
            "Deployment.occurrences_count should reflect occurrences created by save_results",
        )
        self.assertGreater(
            self.deployment.taxa_count,
            0,
            "Deployment.taxa_count should reflect taxa from occurrences created by save_results",
        )


class AlgorithmProjectTestBase(APITestCase):
    """Shared fixture for the two project-scoped algorithm listings.

    Project A has an enabled pipeline carrying one algorithm that ran ("Algo Used")
    and one that never did ("Algo Configured Unused"), plus a disabled pipeline whose
    algorithm's determinations survive ("Algo Superseded"). Project B has its own
    used algorithm. "Algo Orphan" belongs to no pipeline and never ran anywhere.
    """

    def setUp(self):
        from ami.ml.models import ProjectPipelineConfig

        self.user = User.objects.create_user(email="algos@example.com", is_staff=True)  # type: ignore
        self.project = Project.objects.create(name="Algo Project A", create_defaults=False)
        self.other_project = Project.objects.create(name="Algo Project B", create_defaults=False)

        # Project A: an enabled-pipeline algorithm that has run, and one that never did.
        self.algo_used = Algorithm.objects.create(name="Algo Used", version=1)
        self.algo_configured_unused = Algorithm.objects.create(name="Algo Configured Unused", version=1)
        # Project A: an old version on a now-disabled pipeline, whose determinations survive.
        self.algo_superseded = Algorithm.objects.create(name="Algo Superseded", version=1)
        # Project B: a different algorithm, also used.
        self.algo_other_project = Algorithm.objects.create(name="Algo Other Project", version=1)
        # Unrelated algorithm attached to no pipeline and never run.
        self.algo_orphan = Algorithm.objects.create(name="Algo Orphan", version=1)

        enabled_pipeline = Pipeline.objects.create(name="Enabled Pipeline")
        enabled_pipeline.algorithms.add(self.algo_used, self.algo_configured_unused)
        ProjectPipelineConfig.objects.create(project=self.project, pipeline=enabled_pipeline, enabled=True)

        disabled_pipeline = Pipeline.objects.create(name="Disabled Pipeline")
        disabled_pipeline.algorithms.add(self.algo_superseded)
        ProjectPipelineConfig.objects.create(project=self.project, pipeline=disabled_pipeline, enabled=False)

        other_pipeline = Pipeline.objects.create(name="Other Project Pipeline")
        other_pipeline.algorithms.add(self.algo_other_project)
        ProjectPipelineConfig.objects.create(project=self.other_project, pipeline=other_pipeline, enabled=True)

        self._classify_in_project(self.algo_used, self.project)
        self._classify_in_project(self.algo_superseded, self.project)
        self._classify_in_project(self.algo_other_project, self.other_project)

        self.client.force_authenticate(user=self.user)

    def _classify_in_project(self, algorithm, project):
        """Give ``algorithm`` a classification whose capture belongs to ``project``."""
        source_image = SourceImage.objects.create(project=project)
        detection = Detection.objects.create(source_image=source_image)
        return Classification.objects.create(
            detection=detection,
            algorithm=algorithm,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )


class TestAlgorithmViewSetProjectFilter(AlgorithmProjectTestBase):
    """
    The algorithm list endpoint scoped to a project shows what the project can run:
    the algorithms on its enabled pipelines.

    It reflects configuration, not history — a freshly configured project sees its
    algorithms before anything has run, and an algorithm only on a disabled pipeline
    is not offered even if it ran in the past. The algorithms that actually produced
    results are served separately as occurrence filter choices (see
    TestOccurrenceAlgorithmChoices), and detail pages stay reachable for any
    algorithm through the unscoped detail endpoint.
    """

    def _list_algorithm_names(self, project_id=None):
        params = {"project_id": project_id} if project_id is not None else {}
        url = reverse_with_params("api:algorithm-list", params=params)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return {row["name"] for row in response.json()["results"]}

    def test_project_list_shows_enabled_pipeline_algorithms(self):
        """The scoped list is exactly the enabled pipelines' algorithms — including
        one that has never run, so a new project can see what it is set up to use
        before any job has completed."""
        names = self._list_algorithm_names(project_id=self.project.pk)
        self.assertEqual(names, {"Algo Used", "Algo Configured Unused"})

    def test_disabled_pipeline_algorithm_is_not_listed(self):
        """An algorithm only on a pipeline the project has disabled is not part of
        what the project can run, even though its past determinations survive. Those
        stay reachable through the occurrence filter choices and the detail endpoint."""
        names = self._list_algorithm_names(project_id=self.project.pk)
        self.assertNotIn("Algo Superseded", names)

    def test_other_project_only_sees_its_own_algorithms(self):
        names = self._list_algorithm_names(project_id=self.other_project.pk)
        self.assertEqual(names, {"Algo Other Project"})

    def test_unscoped_request_returns_all_algorithms(self):
        """Without project_id, current behavior lists all algorithms (unchanged)."""
        names = self._list_algorithm_names()
        for name in (
            "Algo Used",
            "Algo Superseded",
            "Algo Configured Unused",
            "Algo Other Project",
            "Algo Orphan",
        ):
            self.assertIn(name, names)

    def test_detail_endpoint_unscoped_even_with_project_id(self):
        """Detail stays unscoped so a link from a historical classification — here an
        algorithm outside the project's enabled set — still resolves to its details
        and category map."""
        url = reverse_with_params(
            "api:algorithm-detail",
            kwargs={"pk": self.algo_orphan.pk},
            params={"project_id": self.project.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Algo Orphan")


class TestOccurrenceAlgorithmChoices(AlgorithmProjectTestBase):
    """
    The occurrence filter's algorithm choices, served at /occurrences/algorithms/,
    are exactly the algorithms that produced results in the project.

    An algorithm qualifies by owning output rows: a detection made by it (detectors,
    which never author a Classification) or a classification from it (classifiers and
    standalone post-processing algorithms such as class masking). A superseded
    pipeline version stays a choice as long as its results survive, and a configured
    algorithm that never ran is not offered — the filter never lists a value with
    zero matching occurrences.
    """

    def _choice_names(self, project_id):
        url = reverse_with_params("api:occurrence-algorithms", params={"project_id": project_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return {row["name"] for row in response.json()["results"]}

    def test_choices_are_exactly_the_algorithms_that_produced_results(self):
        """The classifier that ran and the superseded version whose determinations
        survive are choices; the enabled pipeline's never-run algorithm is not.
        This pins the semantic that choices follow results, not setup."""
        names = self._choice_names(self.project.pk)
        self.assertEqual(names, {"Algo Used", "Algo Superseded"})

    def test_configured_but_never_run_algorithm_is_not_a_choice(self):
        """Filtering by an algorithm that never produced a result would always return
        zero occurrences, so configuration alone does not admit one."""
        names = self._choice_names(self.project.pk)
        self.assertNotIn("Algo Configured Unused", names)

    def test_detector_that_ran_is_a_choice_although_it_never_classified(self):
        """Detectors set ``Detection.detection_algorithm`` and never write a
        Classification, so they are reachable only through their detections. This pins
        the regression where scoping choices purely by classification authorship
        dropped every localizer."""
        detector = Algorithm.objects.create(name="Algo Detector", version=1, task_type="localization")

        source_image = SourceImage.objects.create(project=self.project)
        Detection.objects.create(source_image=source_image, detection_algorithm=detector)
        self.assertFalse(Classification.objects.filter(algorithm=detector).exists())

        self.assertIn("Algo Detector", self._choice_names(self.project.pk))

    def test_post_processing_algorithm_with_classifications_is_a_choice(self):
        """A post-processing algorithm has no pipeline but produces determinations in
        the project, so it must be offered — otherwise the user cannot filter
        occurrences by the masked result."""
        masked_algo = Algorithm.objects.create(name="Class Masked Classifier", version=1)
        self._classify_in_project(masked_algo, self.project)

        self.assertIn("Class Masked Classifier", self._choice_names(self.project.pk))

    def test_classifications_in_other_project_do_not_leak(self):
        """An algorithm whose classifications live in another project must not appear."""
        other_masked_algo = Algorithm.objects.create(name="Other Project Masked", version=1)
        self._classify_in_project(other_masked_algo, self.other_project)

        self.assertNotIn("Other Project Masked", self._choice_names(self.project.pk))

    def test_project_id_is_required(self):
        """Choices are relative to a project; without one the request is rejected
        rather than listing every algorithm on the platform."""
        url = reverse_with_params("api:occurrence-algorithms")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_response_is_paginated_like_a_list_endpoint(self):
        """The endpoint returns the standard ``{count, results}`` shape the
        frontend's entity picker consumes."""
        url = reverse_with_params("api:occurrence-algorithms", params={"project_id": self.project.pk})
        data = self.client.get(url).json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["results"]), 2)

    def test_used_lookup_is_deduplicated_in_the_database(self):
        """``used_in_project`` matches one classification row per determination, so it
        must deduplicate in SQL rather than in Python.

        Without that, the rows fetched grow with a project's classification count —
        hundreds of thousands on a real masking run — to identify a handful of algorithms.
        The listed names are correct either way, so this asserts the row count of the
        underlying lookup rather than the endpoint's output. The ``.order_by()`` matters:
        Classification's default ordering would otherwise widen the DISTINCT back to one
        row per classification.
        """
        masked_algo = Algorithm.objects.create(name="Chatty Masked Classifier", version=1)
        for _ in range(5):
            self._classify_in_project(masked_algo, self.project)

        lookup = Classification.objects.filter(
            algorithm_id=masked_algo.pk,
            detection__source_image__project=self.project,
        ).values_list("algorithm_id", flat=True)

        self.assertEqual(len(list(lookup)), 5, "The lookup matches one row per classification")
        self.assertEqual(
            len(list(lookup.order_by().distinct())), 1, "Deduplicating collapses them to the one algorithm"
        )
        self.assertIn("Chatty Masked Classifier", self._choice_names(self.project.pk))


class AlgorithmTaxonVisibilityTestBase(APITestCase):
    """Shared fixture for "which models predict this taxon": TaxonViewSet's
    algorithm_id filter, AlgorithmViewSet's taxon_id filter, and the taxon detail
    response's predicted_by_algorithms field.

    One taxon, in one managed taxa list, reached by three algorithms: one offered by a
    public processing service (visible everywhere), one offered by project A's own
    service (visible only to A), and one offered by project B's own service (visible
    only to B — the negative case). A fourth algorithm has no managed list at all.
    """

    def setUp(self):
        from ami.main.models import TaxaList
        from ami.ml.models import ProjectPipelineConfig

        self.user = User.objects.create_user(email="algo-taxon-vis@example.com", is_staff=True)  # type: ignore
        self.project_a = Project.objects.create(name="Algo Taxon Vis Project A", create_defaults=False)
        self.project_b = Project.objects.create(name="Algo Taxon Vis Project B", create_defaults=False)

        self.taxon = Taxon.objects.create(name="Algo Taxon Vis Species", rank=TaxonRank.SPECIES.name)
        # Taxon.visible_for_user() treats a taxon with no project link as superuser-only
        # (see BaseModel.get_project_accessor()); link it to both projects so the
        # non-superuser test user can see it, independent of algorithm visibility.
        self.taxon.projects.add(self.project_a, self.project_b)
        self.taxa_list = TaxaList.objects.create(name="Algo Taxon Vis Managed List")
        self.taxa_list.taxa.add(self.taxon)

        self.algo_public = Algorithm.objects.create(name="Algo Public", version=1, taxa_list=self.taxa_list)
        self.algo_project_a = Algorithm.objects.create(name="Algo Project A", version=1, taxa_list=self.taxa_list)
        self.algo_project_b = Algorithm.objects.create(name="Algo Project B", version=1, taxa_list=self.taxa_list)
        self.algo_no_list = Algorithm.objects.create(name="Algo No List", version=1)

        pipeline_public = Pipeline.objects.create(name="Taxon Vis Pipeline Public")
        pipeline_public.algorithms.add(self.algo_public)
        ProcessingService.objects.create(name="Taxon Vis PS Public", endpoint_url=None, is_public=True).pipelines.add(
            pipeline_public
        )

        pipeline_a = Pipeline.objects.create(name="Taxon Vis Pipeline A")
        pipeline_a.algorithms.add(self.algo_project_a, self.algo_no_list)
        ProcessingService.objects.create(name="Taxon Vis PS A", endpoint_url=None).pipelines.add(pipeline_a)
        ProjectPipelineConfig.objects.create(project=self.project_a, pipeline=pipeline_a, enabled=True)

        pipeline_b = Pipeline.objects.create(name="Taxon Vis Pipeline B")
        pipeline_b.algorithms.add(self.algo_project_b)
        ProcessingService.objects.create(name="Taxon Vis PS B", endpoint_url=None).pipelines.add(pipeline_b)
        ProjectPipelineConfig.objects.create(project=self.project_b, pipeline=pipeline_b, enabled=True)

        self.client.force_authenticate(user=self.user)


class TestAlgorithmVisibleToProjectQuerySet(AlgorithmTaxonVisibilityTestBase):
    """Unit-level pin for Algorithm.objects.visible_to_project(), the one place the
    three API surfaces below all resolve visibility through."""

    def test_public_algorithm_is_visible_with_no_project(self):
        names = set(Algorithm.objects.visible_to_project(None).values_list("name", flat=True))
        self.assertIn("Algo Public", names)

    def test_public_algorithm_is_visible_to_every_project(self):
        names = set(Algorithm.objects.visible_to_project(self.project_b).values_list("name", flat=True))
        self.assertIn("Algo Public", names)

    def test_project_scoped_algorithm_is_visible_only_to_its_own_project(self):
        names_a = set(Algorithm.objects.visible_to_project(self.project_a).values_list("name", flat=True))
        names_b = set(Algorithm.objects.visible_to_project(self.project_b).values_list("name", flat=True))
        self.assertIn("Algo Project A", names_a)
        self.assertNotIn("Algo Project A", names_b)

    def test_no_project_hides_every_project_scoped_algorithm(self):
        names = set(Algorithm.objects.visible_to_project(None).values_list("name", flat=True))
        self.assertNotIn("Algo Project A", names)
        self.assertNotIn("Algo Project B", names)


class TestAlgorithmViewSetTaxonIdFilter(AlgorithmTaxonVisibilityTestBase):
    """AlgorithmViewSet's ?taxon_id= filter: algorithms whose managed list contains
    the taxon, restricted to what's visible to the active project."""

    def _names(self, **params):
        url = reverse_with_params("api:algorithm-list", params=params)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {row["name"] for row in response.json()["results"]}

    def test_returns_public_and_own_project_algorithms(self):
        names = self._names(project_id=self.project_a.pk, taxon_id=self.taxon.pk)
        self.assertEqual(names, {"Algo Public", "Algo Project A"})

    def test_never_includes_another_projects_algorithm(self):
        """The one negative test that matters: project A never sees project B's
        algorithm for this taxon, even though it predicts the same species."""
        names = self._names(project_id=self.project_a.pk, taxon_id=self.taxon.pk)
        self.assertNotIn("Algo Project B", names)

    def test_with_no_project_id_only_public_algorithms_are_visible(self):
        names = self._names(taxon_id=self.taxon.pk)
        self.assertEqual(names, {"Algo Public"})

    def test_invalid_taxon_id_returns_400(self):
        url = reverse_with_params("api:algorithm-list", params={"taxon_id": "not-a-number"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestTaxonAlgorithmIdFilter(AlgorithmTaxonVisibilityTestBase):
    """TaxonViewSet's ?algorithm_id= filter: taxa in the algorithm's managed list,
    with the algorithm itself resolved through the shared visibility rule first."""

    def _taxon_ids(self, **params):
        params.setdefault("include_unobserved", "true")
        url = reverse_with_params("api:taxon-list", params=params)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {row["id"] for row in response.json()["results"]}

    def test_returns_the_algorithms_managed_taxa(self):
        ids = self._taxon_ids(project_id=self.project_a.pk, algorithm_id=self.algo_public.pk)
        self.assertIn(self.taxon.pk, ids)

    def test_algorithm_private_to_another_project_yields_no_taxa(self):
        """The negative case from the algorithm's side: asking project A for the taxa
        of project B's private algorithm resolves the algorithm as invisible, so the
        result is empty rather than an error or a leak of B's taxa."""
        ids = self._taxon_ids(project_id=self.project_a.pk, algorithm_id=self.algo_project_b.pk)
        self.assertEqual(ids, set())

    def test_algorithm_with_no_managed_list_yields_no_taxa_not_an_error(self):
        response = self.client.get(
            reverse_with_params(
                "api:taxon-list", params={"algorithm_id": self.algo_no_list.pk, "include_unobserved": "true"}
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["results"], [])

    def test_invalid_algorithm_id_returns_400(self):
        url = reverse_with_params("api:taxon-list", params={"algorithm_id": "not-a-number"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestTaxonDetailPredictedByAlgorithms(AlgorithmTaxonVisibilityTestBase):
    """The taxon detail response's predicted_by_algorithms field: only on detail (not
    list rows), scoped by the same visibility rule as the two filters above."""

    def _detail(self, project):
        url = reverse_with_params("api:taxon-detail", kwargs={"pk": self.taxon.pk}, params={"project_id": project.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    def test_lists_public_and_own_project_algorithms(self):
        names = {row["name"] for row in self._detail(self.project_a)["predicted_by_algorithms"]}
        self.assertEqual(names, {"Algo Public", "Algo Project A"})

    def test_never_names_another_projects_algorithm(self):
        names = {row["name"] for row in self._detail(self.project_a)["predicted_by_algorithms"]}
        self.assertNotIn("Algo Project B", names)

    def test_row_shape_is_id_name_key_only(self):
        row = next(r for r in self._detail(self.project_a)["predicted_by_algorithms"] if r["name"] == "Algo Public")
        self.assertEqual(set(row.keys()), {"id", "name", "key"})

    def test_list_rows_do_not_carry_the_field(self):
        """The field is deliberately detail-only; TaxonListSerializer has no such cost
        per row on a page of results."""
        url = reverse_with_params("api:taxon-list", params={"include_unobserved": "true"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("predicted_by_algorithms", response.json()["results"][0])


@override_settings(CACHALOT_ENABLED=False)
class TestTaxonDetailPredictedByAlgorithmsQueryCount(AlgorithmTaxonVisibilityTestBase):
    """Pins the query count for the taxon detail field against a multi-algorithm
    fixture, so a future change that makes it per-row (e.g. N+1 through taxa_list) is
    noticed. Run alone if cachalot state from another test class leaks in — see
    docs/claude/reference (cachalot_disabled leaks on exception)."""

    def test_query_count_does_not_grow_with_the_number_of_algorithms(self):
        from cachalot.api import cachalot_disabled

        url = reverse_with_params(
            "api:taxon-detail", kwargs={"pk": self.taxon.pk}, params={"project_id": self.project_a.pk}
        )
        with cachalot_disabled(), CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["predicted_by_algorithms"]), 2)
        # Baseline is the existing (pre-predicted_by_algorithms) taxon detail cost, plus
        # exactly one query for predicted_by_algorithms — a single join across
        # pipelines/processing_services/project_pipeline_configs/taxa_list/taxa, not one
        # per algorithm. A regression that queries per algorithm row would grow this
        # count with the fixture's algorithm count (currently 3).
        self.assertEqual(len(ctx.captured_queries), 15, "\n".join(q["sql"] for q in ctx.captured_queries))


class TestManagedTaxaListSkipsDescendantExpansion(APITestCase):
    """A managed taxa list (TaxaList.is_managed) always matches exact membership for
    ?taxa_list_id=, ignoring include_descendants — see the note in
    TaxonTaxaListFilter._get_filter(). A curated (unmanaged) list keeps the original
    descendant-expansion behavior; that's a real feature there, unaffected by this rule.

    Both lists have the same shape — containing only the parent taxon, with a child
    (parents_json pointing at the parent) left out — so the only variable is
    is_managed.
    """

    def setUp(self):
        from ami.main.models import TaxaList

        self.user = User.objects.create_user(email="managed-descendants@example.com", is_staff=True)  # type: ignore
        self.project = Project.objects.create(name="Managed Descendants Project", create_defaults=False)

        self.parent = Taxon.objects.create(name="Managed Descendants Genus", rank=TaxonRank.GENUS.name)
        self.child = Taxon.objects.create(
            name="Managed Descendants Species", rank=TaxonRank.SPECIES.name, parent=self.parent
        )
        self.child.update_parents()
        self.parent.projects.add(self.project)
        self.child.projects.add(self.project)

        self.managed_list = TaxaList.objects.create(name="Managed Descendants Managed List")
        self.managed_list.taxa.add(self.parent)
        Algorithm.objects.create(name="Managed Descendants Algo", version=1, taxa_list=self.managed_list)

        self.unmanaged_list = TaxaList.objects.create(name="Managed Descendants Curated List")
        self.unmanaged_list.taxa.add(self.parent)

        self.client.force_authenticate(self.user)

    def _taxon_names(self, taxa_list_id):
        url = reverse_with_params(
            "api:taxon-list",
            params={"project_id": self.project.pk, "taxa_list_id": taxa_list_id, "include_unobserved": "true"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {row["name"] for row in response.json()["results"]}

    def test_managed_list_returns_only_its_own_taxa(self):
        """The child is a real descendant (its parents_json contains the parent), but
        the managed list must not claim the algorithm predicts it."""
        names = self._taxon_names(self.managed_list.pk)
        self.assertEqual(names, {self.parent.name})

    def test_unmanaged_curated_list_still_expands_to_descendants(self):
        """Same shape, but a hand-curated list's descendant expansion is a real,
        unaffected feature — the fix must not widen past managed lists."""
        names = self._taxon_names(self.unmanaged_list.pk)
        self.assertEqual(names, {self.parent.name, self.child.name})
