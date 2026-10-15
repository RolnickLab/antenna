"""
Occurrence sets: a fixed list of occurrences, decided once.

The point of the model is that the list does not move. Anything comparing results over
time — scoring two classifiers, re-running an export — is only meaningful if both runs saw
the same occurrences. So these tests are mostly about what the API refuses.
"""

import datetime
import uuid

from rest_framework import status
from rest_framework.test import APITestCase

from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Event,
    Occurrence,
    OccurrenceSet,
    Project,
    S3StorageSource,
    SourceImage,
    Taxon,
    TaxonRank,
)
from ami.users.models import User
from ami.users.roles import BasicMember, MLDataManager


class OccurrenceSetFixture(APITestCase):
    """
    Occurrences are created directly rather than through the capture fixtures.

    These tests are about what the endpoint accepts and refuses, and need nothing from a
    detection. Going through create_captures/create_occurrences pulls in event grouping and
    a storage read for image dimensions, neither of which works in a test, and the failures
    land at random on whichever test ran first.
    """

    def setUp(self) -> None:
        self.owner = User.objects.create_user(email="owner@example.com", password="testpass123")
        self.curator = User.objects.create_user(email="curator@example.com", password="testpass123")
        self.member = User.objects.create_user(email="member@example.com", password="testpass123")

        self.project = Project.objects.create(name="Set Project", owner=self.owner)
        MLDataManager.assign_user(self.curator, self.project)
        BasicMember.assign_user(self.member, self.project)

        self.occurrences = [self.make_occurrence(self.project) for _ in range(3)]
        self.url = "/api/v2/occurrences/sets/"

    @staticmethod
    def make_occurrence(project: Project) -> Occurrence:
        """
        One occurrence the list endpoint will actually return.

        Built here rather than through the capture fixtures, which time their images from
        the current clock and group them into events by reading image dimensions from
        storage. Neither works in a test, and the failures land at random on whichever test
        ran first. The list only shows occurrences with a real detection and a
        determination, so both are set.
        """
        storage = S3StorageSource.objects.create(name=f"source {uuid.uuid4().hex[:6]}", project=project, bucket="test")
        deployment = Deployment.objects.create(
            name=f"station {uuid.uuid4().hex[:6]}", project=project, data_source=storage
        )
        night = datetime.datetime(2026, 6, 1, 22, 0, 0, tzinfo=datetime.timezone.utc)
        event = Event.objects.create(deployment=deployment, project=project, start=night)
        image = SourceImage.objects.create(
            deployment=deployment,
            project=project,
            event=event,
            timestamp=night,
            path=f"test/{uuid.uuid4().hex[:8]}.jpg",
        )
        taxon = Taxon.objects.create(name=f"Testus {uuid.uuid4().hex[:6]}", rank=TaxonRank.SPECIES.name)
        taxon.projects.add(project)
        detection = Detection.objects.create(source_image=image, timestamp=night, bbox=[0.1, 0.1, 0.2, 0.2])
        Classification.objects.create(detection=detection, taxon=taxon, score=0.9, timestamp=night)
        occurrence = detection.associate_new_occurrence()
        occurrence.refresh_from_db()
        return occurrence

    def _create(self, user, **overrides):
        payload = {
            "name": "Blind set",
            "description": "",
            "project_id": self.project.pk,
            "occurrence_ids": [o.pk for o in self.occurrences],
        }
        payload.update(overrides)
        self.client.force_authenticate(user=user)
        return self.client.post(self.url, payload, format="json")


class TestCreatingASet(OccurrenceSetFixture):
    def test_a_curator_can_create_one(self):
        response = self._create(self.curator)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        created = OccurrenceSet.objects.get(pk=response.data["id"])
        self.assertEqual(created.occurrences.count(), 3)
        self.assertEqual(list(created.projects.all()), [self.project])

    def test_a_member_without_the_permission_cannot(self):
        response = self._create(self.member)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(OccurrenceSet.objects.exists())

    def test_an_anonymous_caller_cannot(self):
        response = self._create(None)

        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.assertFalse(OccurrenceSet.objects.exists())

    def test_an_occurrence_from_another_project_is_refused(self):
        """Otherwise a set quietly reaches into data its project cannot see."""
        other = Project.objects.create(name="Other Project", owner=self.owner)
        outsider = self.make_occurrence(other)

        response = self._create(self.curator, occurrence_ids=[self.occurrences[0].pk, outsider.pk])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("occurrence_ids", response.data)
        self.assertFalse(OccurrenceSet.objects.exists())

    def test_an_empty_set_is_refused(self):
        response = self._create(self.curator, occurrence_ids=[])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestMembershipDoesNotMove(OccurrenceSetFixture):
    def setUp(self) -> None:
        super().setUp()
        self.set = OccurrenceSet.objects.create(name="Blind set")
        self.set.projects.add(self.project)
        self.set.occurrences.add(*self.occurrences)
        self.detail_url = f"{self.url}{self.set.pk}/"
        self.client.force_authenticate(user=self.curator)

    def test_the_occurrences_cannot_be_changed(self):
        response = self.client.patch(self.detail_url, {"occurrence_ids": [self.occurrences[0].pk]}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.set.occurrences.count(), 3)

    def test_the_name_and_description_can_be_changed(self):
        response = self.client.patch(self.detail_url, {"name": "Renamed", "description": "why"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.set.refresh_from_db()
        self.assertEqual(self.set.name, "Renamed")

    def test_there_is_no_put(self):
        """A full replace would carry the occurrences with it."""
        response = self.client.put(self.detail_url, {"name": "Replaced"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_a_curator_can_delete_one(self):
        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(OccurrenceSet.objects.filter(pk=self.set.pk).exists())


class TestFilteringOccurrencesBySet(OccurrenceSetFixture):
    """The occurrence list can be narrowed to one set, which is how a set is reviewed."""

    def setUp(self) -> None:
        super().setUp()
        self.set = OccurrenceSet.objects.create(name="Blind set")
        self.set.projects.add(self.project)
        self.set.occurrences.add(self.occurrences[0], self.occurrences[1])
        self.client.force_authenticate(user=self.curator)

    def _ids(self, **params):
        # apply_defaults=false: the list hides occurrences without a determination or a
        # score by default, and these fixtures are bare rows made to exercise the filter.
        response = self.client.get(
            "/api/v2/occurrences/",
            {"project_id": self.project.pk, "apply_defaults": "false", **params},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return {row["id"] for row in response.data["results"]}

    def test_only_the_sets_occurrences_come_back(self):
        self.assertEqual(
            self._ids(occurrence_set=self.set.pk),
            {self.occurrences[0].pk, self.occurrences[1].pk},
        )

    def test_without_the_filter_every_occurrence_comes_back(self):
        self.assertEqual(self._ids(), {o.pk for o in self.occurrences})


class TestGlobalSets(OccurrenceSetFixture):
    def setUp(self) -> None:
        super().setUp()
        self.global_set = OccurrenceSet.objects.create(name="Platform-wide set")
        self.client.force_authenticate(user=self.curator)

    def _names(self, response):
        return [row["name"] for row in response.data["results"]]

    def test_a_global_set_is_offered_to_every_project(self):
        response = self.client.get(self.url, {"project_id": self.project.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.global_set.name, self._names(response))

    def test_a_global_set_cannot_be_edited_through_the_api(self):
        """It has no single project whose permissions would govern it."""
        response = self.client.patch(f"{self.url}{self.global_set.pk}/", {"name": "Mine now"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.global_set.refresh_from_db()
        self.assertEqual(self.global_set.name, "Platform-wide set")


class TestListing(OccurrenceSetFixture):
    def setUp(self) -> None:
        super().setUp()
        self.set = OccurrenceSet.objects.create(name="Blind set")
        self.set.projects.add(self.project)
        self.set.occurrences.add(*self.occurrences)

    def test_a_project_is_required(self):
        """Without one the endpoint would list every set on the platform."""
        self.client.force_authenticate(user=self.curator)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_size_is_reported_without_the_occurrences(self):
        self.client.force_authenticate(user=self.curator)
        response = self.client.get(self.url, {"project_id": self.project.pk})

        row = next(r for r in response.data["results"] if r["name"] == "Blind set")
        self.assertEqual(row["occurrences_count"], 3)
        self.assertNotIn("occurrences", row)

    def test_another_project_does_not_see_it(self):
        other = Project.objects.create(name="Other Project", owner=self.owner)
        MLDataManager.assign_user(self.curator, other)
        self.client.force_authenticate(user=self.curator)

        response = self.client.get(self.url, {"project_id": other.pk})

        self.assertNotIn("Blind set", [row["name"] for row in response.data["results"]])
