"""
Occurrence sets through the API: creating, listing and choosing them, and filtering the
occurrence list by one. Most of these tests are about what the API refuses, because a
set is only useful if its list of occurrences does not move. See #763.
"""

import datetime
import re
import uuid

from django.db import connection
from django.test.utils import CaptureQueriesContext
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
from ami.tests.fixtures.queries import no_query_cache
from ami.users.models import User
from ami.users.roles import BasicMember, MLDataManager

SETS_URL = "/api/v2/occurrences/sets/"
OCCURRENCES_URL = "/api/v2/occurrences/"


def make_bare_occurrences(project: Project, count: int) -> list[Occurrence]:
    # Enough for create and listing, which only need rows to point at.
    return Occurrence.objects.bulk_create([Occurrence(project=project) for _ in range(count)])


def make_listed_occurrence(project: Project, score: float = 0.9) -> Occurrence:
    """
    One occurrence the occurrence list will return: it has a real detection and a
    determination.

    Built directly rather than through the capture fixtures, which time images from the
    current clock and read image dimensions from storage, so their failures land at
    random on whichever test ran first.
    """
    storage = S3StorageSource.objects.create(name=f"source {uuid.uuid4().hex[:6]}", project=project, bucket="test")
    deployment = Deployment.objects.create(
        name=f"station {uuid.uuid4().hex[:6]}", project=project, data_source=storage
    )
    night = datetime.datetime(2026, 6, 1, 22, 0, 0)
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
    Classification.objects.create(detection=detection, taxon=taxon, score=score, timestamp=night)
    occurrence = detection.associate_new_occurrence()
    occurrence.refresh_from_db()
    return occurrence


def make_set(name: str, projects: list[Project], occurrences: list[Occurrence] | None = None) -> OccurrenceSet:
    occurrence_set = OccurrenceSet.objects.create(name=name)
    occurrence_set.projects.set(projects)
    occurrence_set.occurrences.set(occurrences or [])
    return occurrence_set


class OccurrenceSetAPITestCase(APITestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(email="owner@example.com")
        self.curator = User.objects.create_user(email="curator@example.com")
        self.member = User.objects.create_user(email="member@example.com")
        self.outsider = User.objects.create_user(email="outsider@example.com")
        self.superuser = User.objects.create_superuser(email="admin@example.com", password="x")

        self.project = Project.objects.create(name="Set project", owner=self.owner, create_defaults=False)
        self.other_project = Project.objects.create(name="Other project", owner=self.owner, create_defaults=False)
        MLDataManager.assign_user(self.curator, self.project)
        BasicMember.assign_user(self.member, self.project)

        self.occurrences = make_bare_occurrences(self.project, 3)

    def post_set(self, user: User | None, query: str = "", **overrides):
        payload = {
            "name": "Blind set",
            "description": "",
            "project_id": self.project.pk,
            "occurrence_ids": [o.pk for o in self.occurrences],
        }
        payload.update(overrides)
        self.client.force_authenticate(user=user)
        return self.client.post(f"{SETS_URL}{query}", payload, format="json")


class TestCreatingASet(OccurrenceSetAPITestCase):
    def test_only_users_with_the_create_permission_can_create_one(self):
        cases = [
            (self.curator, status.HTTP_201_CREATED),
            (self.superuser, status.HTTP_201_CREATED),
            (self.member, status.HTTP_403_FORBIDDEN),
            (self.outsider, status.HTTP_403_FORBIDDEN),
            (None, status.HTTP_401_UNAUTHORIZED),
        ]
        for user, expected in cases:
            with self.subTest(user=user):
                response = self.post_set(user)
                self.assertEqual(response.status_code, expected, response.data)
        self.assertEqual(OccurrenceSet.objects.count(), 2)

    def test_the_new_set_holds_the_given_occurrences_in_the_given_project(self):
        response = self.post_set(self.curator)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        created = OccurrenceSet.objects.get(pk=response.data["id"])
        self.assertEqual(set(created.occurrences.values_list("pk", flat=True)), {o.pk for o in self.occurrences})
        self.assertEqual(list(created.projects.all()), [self.project])
        self.assertEqual(response.data["occurrences_count"], 3)

    def test_a_project_id_that_is_not_an_integer_is_refused(self):
        response = self.post_set(self.curator, project_id="abc")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("project_id", response.data)

    def test_a_project_that_does_not_exist_is_refused(self):
        response = self.post_set(self.curator, project_id=999999)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("project_id", response.data)

    def test_the_project_comes_from_the_payload_not_the_query_string(self):
        """Otherwise permission in one project would allow writing a set into another."""
        response = self.post_set(
            self.curator, query=f"?project_id={self.project.pk}", project_id=self.other_project.pk
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(OccurrenceSet.objects.exists())

    def test_occurrences_outside_the_project_are_refused_by_id(self):
        outsider = make_bare_occurrences(self.other_project, 1)[0]
        missing_id = outsider.pk + 1000

        response = self.post_set(self.curator, occurrence_ids=[self.occurrences[0].pk, outsider.pk, missing_id])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        named = str(response.data["occurrence_ids"][0]).split(":", 1)[1]
        self.assertEqual({int(pk) for pk in re.findall(r"\d+", named)}, {outsider.pk, missing_id})
        self.assertFalse(OccurrenceSet.objects.exists())

    def test_an_empty_list_is_refused(self):
        response = self.post_set(self.curator, occurrence_ids=[])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(OccurrenceSet.objects.exists())

    def test_query_count_does_not_grow_with_the_number_of_occurrences(self):
        def queries_to_create(count: int) -> int:
            ids = [o.pk for o in make_bare_occurrences(self.project, count)]
            with no_query_cache(), CaptureQueriesContext(connection) as queries:
                response = self.post_set(self.curator, occurrence_ids=ids)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
            return len(queries)

        self.assertEqual(queries_to_create(50), queries_to_create(5))


class TestMembershipIsFrozen(OccurrenceSetAPITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.set = make_set("Blind set", [self.project], self.occurrences)
        self.detail_url = f"{SETS_URL}{self.set.pk}/"

    def test_the_occurrences_cannot_be_changed(self):
        self.client.force_authenticate(user=self.curator)
        response = self.client.patch(self.detail_url, {"occurrence_ids": [self.occurrences[0].pk]}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.set.occurrences.count(), 3)

    def test_the_project_cannot_be_changed(self):
        MLDataManager.assign_user(self.curator, self.other_project)
        self.client.force_authenticate(user=self.curator)
        response = self.client.patch(self.detail_url, {"project_id": self.other_project.pk}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(list(self.set.projects.all()), [self.project])

    def test_there_is_no_put(self):
        """A full replace would carry the occurrences with it."""
        self.client.force_authenticate(user=self.curator)
        response = self.client.put(self.detail_url, {"name": "Replaced"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_only_users_with_the_update_permission_can_rename_it(self):
        cases = [
            (self.curator, status.HTTP_200_OK),
            (self.superuser, status.HTTP_200_OK),
            (self.member, status.HTTP_403_FORBIDDEN),
            (self.outsider, status.HTTP_403_FORBIDDEN),
            (None, status.HTTP_401_UNAUTHORIZED),
        ]
        for user, expected in cases:
            with self.subTest(user=user):
                self.client.force_authenticate(user=user)
                response = self.client.patch(self.detail_url, {"name": f"Renamed by {user}"}, format="json")
                self.assertEqual(response.status_code, expected, response.data)

    def test_only_users_with_the_delete_permission_can_delete_it(self):
        cases = [
            (None, status.HTTP_401_UNAUTHORIZED),
            (self.outsider, status.HTTP_403_FORBIDDEN),
            (self.member, status.HTTP_403_FORBIDDEN),
            (self.curator, status.HTTP_204_NO_CONTENT),
        ]
        for user, expected in cases:
            with self.subTest(user=user):
                self.client.force_authenticate(user=user)
                self.assertEqual(self.client.delete(self.detail_url).status_code, expected)
        self.assertFalse(OccurrenceSet.objects.filter(pk=self.set.pk).exists())


class TestPublicSets(OccurrenceSetAPITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.public_set = make_set("Public set", [])

    def test_a_public_set_is_offered_to_every_project(self):
        self.client.force_authenticate(user=self.outsider)
        for project in (self.project, self.other_project):
            with self.subTest(project=project):
                response = self.client.get(SETS_URL, {"project_id": project.pk})
                self.assertIn("Public set", [row["name"] for row in response.data["results"]])

    def test_a_public_set_cannot_be_changed_through_the_api(self):
        """No project's permissions govern it, so not even a superuser changes it here."""
        self.client.force_authenticate(user=self.superuser)
        url = f"{SETS_URL}{self.public_set.pk}/"

        self.assertEqual(self.client.patch(url, {"name": "Mine now"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.public_set.refresh_from_db()
        self.assertEqual(self.public_set.name, "Public set")


class TestListingSets(OccurrenceSetAPITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.set = make_set("Blind set", [self.project], self.occurrences)

    def names(self, user: User | None, project: Project, url: str = SETS_URL) -> list[str]:
        self.client.force_authenticate(user=user)
        response = self.client.get(url, {"project_id": project.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return [row["name"] for row in response.data["results"]]

    def test_a_project_is_required(self):
        """Without one the endpoint would list every set on the platform."""
        self.client.force_authenticate(user=self.curator)
        for url in (SETS_URL, f"{SETS_URL}choices/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status.HTTP_400_BAD_REQUEST)

    def test_another_project_does_not_see_it(self):
        self.assertNotIn("Blind set", self.names(self.curator, self.other_project))

    def test_a_draft_projects_sets_are_hidden_from_non_members(self):
        draft = Project.objects.create(name="Draft project", owner=self.owner, draft=True, create_defaults=False)
        BasicMember.assign_user(self.member, draft)
        make_set("Draft set", [draft])

        for user, visible in [(self.member, True), (self.outsider, False), (None, False)]:
            with self.subTest(user=user):
                self.assertEqual("Draft set" in self.names(user, draft), visible)

    def test_rows_report_the_size_but_not_the_occurrences(self):
        self.client.force_authenticate(user=self.curator)
        row = self.client.get(SETS_URL, {"project_id": self.project.pk}).data["results"][0]

        self.assertEqual(row["occurrences_count"], 3)
        self.assertNotIn("occurrences", row)
        self.assertNotIn("occurrence_ids", row)

    def test_rows_offer_edit_actions_only_to_users_who_may_take_them(self):
        for user, expected in [(self.curator, {"update", "delete"}), (self.member, set())]:
            with self.subTest(user=user):
                self.client.force_authenticate(user=user)
                row = self.client.get(SETS_URL, {"project_id": self.project.pk}).data["results"][0]
                self.assertEqual(set(row["user_permissions"]), expected)

    def test_choices_are_most_recently_updated_first(self):
        make_set("Newer set", [self.project])
        self.set.save()  # now the most recently updated

        self.assertEqual(self.names(self.curator, self.project, f"{SETS_URL}choices/"), ["Blind set", "Newer set"])

    def test_query_count_does_not_grow_with_the_number_of_sets(self):
        def queries_to_list(url: str) -> int:
            self.client.force_authenticate(user=self.curator)
            with no_query_cache(), CaptureQueriesContext(connection) as queries:
                response = self.client.get(url, {"project_id": self.project.pk})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            return len(queries)

        for url in (SETS_URL, f"{SETS_URL}choices/"):
            with self.subTest(url=url):
                one = queries_to_list(url)
                for i in range(2):
                    make_set(f"Extra {url} {i}", [self.project], self.occurrences)
                self.assertEqual(queries_to_list(url), one)


class TestFilteringOccurrencesBySet(OccurrenceSetAPITestCase):
    """The occurrence list can be narrowed to one set, which is how a set is reviewed."""

    def setUp(self) -> None:
        super().setUp()
        self.listed = [make_listed_occurrence(self.project) for _ in range(3)]
        self.set = make_set("Blind set", [self.project], self.listed[:2])
        self.client.force_authenticate(user=self.curator)

    def ids(self, project: Project | None = None, **params) -> set[int]:
        project = project or self.project
        response = self.client.get(OCCURRENCES_URL, {"project_id": project.pk, **params})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return {row["id"] for row in response.data["results"]}

    def test_only_the_sets_occurrences_come_back(self):
        self.assertEqual(self.ids(occurrence_set_id=self.set.pk), {o.pk for o in self.listed[:2]})

    def test_an_id_that_is_not_an_integer_is_refused(self):
        response = self.client.get(OCCURRENCES_URL, {"project_id": self.project.pk, "occurrence_set_id": "abc"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_list_stays_scoped_to_the_active_project(self):
        """A set holding another project's occurrence (made in the admin) does not leak it."""
        foreign = make_listed_occurrence(self.other_project)
        self.set.occurrences.add(foreign)

        self.assertNotIn(foreign.pk, self.ids(occurrence_set_id=self.set.pk))

    def test_the_projects_default_filters_still_apply(self):
        low_score = make_listed_occurrence(self.project, score=0.1)
        self.set.occurrences.add(low_score)
        self.project.default_filters_score_threshold = 0.5
        self.project.save()

        self.assertNotIn(low_score.pk, self.ids(occurrence_set_id=self.set.pk))
        self.assertIn(low_score.pk, self.ids(occurrence_set_id=self.set.pk, apply_defaults="false"))
