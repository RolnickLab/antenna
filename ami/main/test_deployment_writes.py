"""
Background work on a station must not overwrite a user's edits to it.

Regroup, cached-count refreshes and storage syncs hold a copy of the Deployment
loaded before their slow queries. They may write only the fields they compute,
so an edit that commits in the meantime survives. See #1573.
"""

from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from ami.main.models import Deployment, Device, Event, Project, Site, SourceImage, group_images_into_events
from ami.tests.fixtures.main import create_captures, setup_test_project
from ami.tests.fixtures.storage import populate_bucket

EDITED_NAME = "Edited station name"
EDITED_LATITUDE = 12.345


class StationEditTestCase(TestCase):
    """Helpers only; defines no tests."""

    project: Project
    deployment: Deployment

    def _create_edit_targets(self):
        self.new_site = Site.objects.create(name="Edited site", project=self.project)
        self.new_device = Device.objects.create(name="Edited device", project=self.project)

    def _user_edit(self):
        """The edit a user saves in the station form while background work runs."""
        Deployment.objects.filter(pk=self.deployment.pk).update(
            name=EDITED_NAME, latitude=EDITED_LATITUDE, research_site=self.new_site, device=self.new_device
        )

    def _assert_edit_survived(self):
        fresh = Deployment.objects.get(pk=self.deployment.pk)
        self.assertEqual(
            (fresh.name, fresh.latitude, fresh.research_site_id, fresh.device_id),
            (EDITED_NAME, EDITED_LATITUDE, self.new_site.pk, self.new_device.pk),
        )
        return fresh


class TestBackgroundWritesKeepStationEdits(StationEditTestCase):
    def setUp(self):
        self.project, self.deployment = setup_test_project(reuse=False)
        create_captures(self.deployment, num_nights=2, images_per_night=3)
        self._create_edit_targets()

    def _edit_during_timestamp_query(self):
        """Patch the last query of the cached-count refresh so the edit commits mid-refresh."""
        original = Deployment.get_first_and_last_timestamps
        calls = {"n": 0}

        def edit_then_query(instance):
            calls["n"] += 1
            if calls["n"] == 1:
                self._user_edit()
            return original(instance)

        return mock.patch.object(Deployment, "get_first_and_last_timestamps", edit_then_query)

    def test_regroup_keeps_edit_made_while_it_runs(self):
        stale = Deployment.objects.get(pk=self.deployment.pk)  # the regroup task loads the row first
        SourceImage.objects.filter(deployment=stale).update(event=None)
        self._user_edit()

        group_images_into_events(stale)

        self._assert_edit_survived()

    def test_regroup_still_refreshes_cached_counts(self):
        stale = Deployment.objects.get(pk=self.deployment.pk)
        SourceImage.objects.filter(deployment=stale).update(event=None)
        Event.objects.filter(deployment=stale).delete()
        Deployment.objects.filter(pk=stale.pk).update(events_count=0, captures_count=0)
        self._user_edit()

        group_images_into_events(stale)

        fresh = self._assert_edit_survived()
        self.assertEqual(fresh.events_count, Event.objects.filter(deployment=fresh).count())
        self.assertGreater(fresh.events_count, 0)
        self.assertEqual(fresh.captures_count, SourceImage.objects.filter(deployment=fresh).count())

    def test_cached_count_refresh_keeps_edit_made_while_it_runs(self):
        """The path used after saving ML results and at the end of a regroup."""
        stale = Deployment.objects.get(pk=self.deployment.pk)
        with self._edit_during_timestamp_query():
            stale.update_calculated_fields(save=True)
        self._assert_edit_survived()

    def test_project_refresh_keeps_edit_made_while_it_runs(self):
        """The project-wide refresh loads every station before it updates the first one."""
        with self._edit_during_timestamp_query():
            self.project.update_related_calculated_fields()
        self._assert_edit_survived()

    def test_user_save_still_writes_edits_and_counts(self):
        deployment = Deployment.objects.get(pk=self.deployment.pk)
        deployment.name = EDITED_NAME
        deployment.captures_count = 0
        deployment.save(regroup_async=False)

        fresh = Deployment.objects.get(pk=self.deployment.pk)
        self.assertEqual(fresh.name, EDITED_NAME)
        self.assertEqual(fresh.captures_count, SourceImage.objects.filter(deployment=fresh).count())


class TestSyncKeepsStationEdits(StationEditTestCase):
    def setUp(self):
        self.project, self.deployment = setup_test_project(reuse=False)
        assert self.deployment.data_source is not None
        populate_bucket(
            config=self.deployment.data_source.config,
            subdir=f"deployment_{self.deployment.pk}",
            skip_existing=False,
        )
        self._create_edit_targets()

    def _sync_with_edit_during_listing(self, regroup_after: bool):
        stale = Deployment.objects.get(pk=self.deployment.pk)  # the sync job loads the row first
        with mock.patch("ami.main.models._compare_totals_for_sync", side_effect=lambda *args: self._user_edit()):
            stale.sync_captures(regroup_after=regroup_after)
        return self._assert_edit_survived()

    def test_sync_keeps_edit_made_while_it_runs(self):
        fresh = self._sync_with_edit_during_listing(regroup_after=True)
        self.assertGreater(fresh.captures_count, 0)
        self.assertEqual(fresh.events_count, Event.objects.filter(deployment=fresh).count())

    def test_sync_job_path_keeps_edit_made_while_it_runs(self):
        """The data storage sync job syncs without the final regroup and regroups as its own stage."""
        fresh = self._sync_with_edit_during_listing(regroup_after=False)
        self.assertEqual(fresh.captures_count, SourceImage.objects.filter(deployment=fresh).count())
        self.assertIsNotNone(fresh.data_source_last_checked)


class TestStationSaveQueuesRegroupAfterCommit(TestCase):
    def setUp(self):
        self.project, self.deployment = setup_test_project(reuse=False)
        create_captures(self.deployment, num_nights=2, images_per_night=3)
        SourceImage.objects.filter(deployment=self.deployment).update(event=None)  # station needs a regroup
        self.client = APIClient()
        self.client.force_authenticate(self.project.owner)

    def _patch_station(self):
        resp = self.client.patch(
            f"/api/v2/deployments/{self.deployment.pk}/", {"latitude": EDITED_LATITUDE}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_regroup_is_not_queued_before_the_edit_commits(self):
        """A task queued inside the request transaction can read the row as it was before the edit."""
        with mock.patch("ami.tasks.regroup_events.delay") as delay:
            with self.captureOnCommitCallbacks(execute=False):
                self._patch_station()
                self.assertEqual(delay.call_count, 0)

    def test_regroup_is_queued_once_the_edit_commits(self):
        with mock.patch("ami.tasks.regroup_events.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                self._patch_station()
        delay.assert_called_once_with(self.deployment.pk)
