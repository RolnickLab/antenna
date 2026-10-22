"""API tests for occurrence sets. The model tests are in ``test_occurrence_set.py``."""


from django.test import TestCase
from rest_framework.test import APIClient

from ami.main.models import OccurrenceSet, Project, Taxon
from ami.main.models_future.enums import TaxonRank
from ami.tests.fixtures.main import (
    create_captures,
    create_occurrences,
    create_taxa,
    group_images_into_events,
    setup_test_project,
)
from ami.tests.fixtures.queries import no_query_cache
from ami.users.models import User
from ami.users.roles import BasicMember, MLDataManager, ProjectManager

SETS_URL = "/api/v2/occurrences/sets/"
OCCURRENCES_URL = "/api/v2/occurrences/"


class OccurrenceSetTestCase(TestCase):
    """A project with seven occurrences of two species, and a second project with two occurrences."""

    @classmethod
    def setUpTestData(cls):
        cls.project, cls.deployment = setup_test_project(reuse=False)
        create_captures(deployment=cls.deployment, num_nights=1, images_per_night=4, interval_minutes=1)
        group_images_into_events(cls.deployment)
        create_taxa(cls.project)
        taxon_a, taxon_b = Taxon.objects.filter(projects=cls.project, rank=TaxonRank.SPECIES.name).order_by("name")[:2]
        create_occurrences(deployment=cls.deployment, num=4, taxon=taxon_a)
        create_occurrences(deployment=cls.deployment, num=3, taxon=taxon_b)
        cls.occurrence_ids = sorted(cls.project.occurrences.values_list("pk", flat=True))

        cls.other_project, other_deployment = setup_test_project(reuse=False)
        create_captures(deployment=other_deployment, num_nights=1, images_per_night=2, interval_minutes=1)
        group_images_into_events(other_deployment)
        create_occurrences(deployment=other_deployment, num=2, taxon=taxon_a)
        cls.other_occurrence_ids = sorted(cls.other_project.occurrences.values_list("pk", flat=True))

        cls.superuser = User.objects.create_superuser(email="occsets-super@insectai.org", password="x")
        cls.ml_data_manager = cls.create_member("occsets-mldm@insectai.org", MLDataManager)
        cls.project_manager = cls.create_member("occsets-pm@insectai.org", ProjectManager)
        cls.basic_member = cls.create_member("occsets-basic@insectai.org", BasicMember)
        cls.non_member = User.objects.create_user(email="occsets-outsider@insectai.org")

    @classmethod
    def create_member(cls, email: str, role) -> User:
        user = User.objects.create_user(email=email)
        cls.project.members.add(user)
        role.assign_user(user, cls.project)
        return user

    def setUp(self):
        self.client = APIClient()

    def create_set(self, **fields) -> OccurrenceSet:
        fields.setdefault("name", "Flagged")
        fields.setdefault("project", self.project)
        return OccurrenceSet.objects.create(**fields)

    def create_frozen_set(self) -> OccurrenceSet:
        occurrence_set = self.create_set()
        occurrence_set.occurrences.add(*self.occurrence_ids[:2])
        occurrence_set.freeze(self.ml_data_manager)
        return occurrence_set

    def member_ids(self, occurrence_set: OccurrenceSet) -> list[int]:
        return sorted(occurrence_set.occurrences.values_list("pk", flat=True))

    def list_occurrence_ids(self, params: dict) -> list[int]:
        self.client.force_authenticate(self.superuser)
        response = self.client.get(OCCURRENCES_URL, {"project_id": self.project.pk, "limit": 100, **params})
        self.assertEqual(response.status_code, 200, response.content)
        return sorted(row["id"] for row in response.json()["results"])


class TestOccurrenceSetAPI(OccurrenceSetTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.ml_data_manager)

    def test_create(self):
        response = self.client.post(SETS_URL, {"name": "Flagged", "project": self.project.pk}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(
            (data["method"], data["kwargs"], data["populated_at"], data["frozen_at"], data["copied_from"]),
            ("manual", {}, None, None, None),
        )

    def test_invalid_input_is_refused(self):
        cases = {
            "method that does not exist yet": {"method": "filters"},
            "arguments for a manual set": {"kwargs": {"filters": {}}},
            "arguments that are not an object": {"kwargs": "x"},
            "no project": {"project": None},
        }
        for label, change in cases.items():
            with self.subTest(label):
                response = self.client.post(
                    SETS_URL, {"name": label, "project": self.project.pk, **change}, format="json"
                )
                self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(OccurrenceSet.objects.exists())

    def test_project_and_state_fields_cannot_change(self):
        occurrence_set = self.create_set()
        url = f"{SETS_URL}{occurrence_set.pk}/"
        response = self.client.patch(url, {"project": self.other_project.pk}, format="json")
        self.assertEqual(response.status_code, 400, response.content)
        response = self.client.patch(
            url,
            {"frozen_at": "2026-01-01T00:00:00", "populated_at": "2026-01-01T00:00:00", "copied_from": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        occurrence_set.refresh_from_db()
        self.assertEqual(
            (
                occurrence_set.project,
                occurrence_set.frozen_at,
                occurrence_set.populated_at,
                occurrence_set.copied_from,
            ),
            (self.project, None, None, None),
        )

    def test_add_and_remove_occurrences(self):
        occurrence_set = self.create_set()
        add_url = f"{SETS_URL}{occurrence_set.pk}/add/"
        remove_url = f"{SETS_URL}{occurrence_set.pk}/remove/"

        response = self.client.post(add_url, {"occurrence_ids": self.occurrence_ids[:3]}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"occurrence_set": occurrence_set.pk, "occurrences_count": 3})

        # Adding a member again leaves it once.
        response = self.client.post(add_url, {"occurrence_ids": self.occurrence_ids[2:4]}, format="json")
        self.assertEqual(response.json()["occurrences_count"], 4)

        response = self.client.post(remove_url, {"occurrence_ids": [self.occurrence_ids[0]]}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.member_ids(occurrence_set), self.occurrence_ids[1:4])

    def test_invalid_occurrence_ids_are_refused_without_a_partial_write(self):
        occurrence_set = self.create_set()
        cases = {
            "other project": [self.occurrence_ids[0], self.other_occurrence_ids[0]],
            "missing": [self.occurrence_ids[0], 999999999],
            "not a number": ["abc"],
            "empty": [],
            "too many": list(range(1, 1002)),
        }
        for label, occurrence_ids in cases.items():
            for action in ("add", "remove"):
                with self.subTest(label, action=action):
                    response = self.client.post(
                        f"{SETS_URL}{occurrence_set.pk}/{action}/", {"occurrence_ids": occurrence_ids}, format="json"
                    )
                    self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(occurrence_set.occurrences.exists())

    def test_frozen_set_refuses_hand_edits_and_a_second_freeze(self):
        occurrence_set = self.create_frozen_set()
        for action in ("add", "remove"):
            with self.subTest(action=action):
                response = self.client.post(
                    f"{SETS_URL}{occurrence_set.pk}/{action}/",
                    {"occurrence_ids": self.occurrence_ids[2:4]},
                    format="json",
                )
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn("frozen", str(response.json()))
        self.assertEqual(self.client.post(f"{SETS_URL}{occurrence_set.pk}/freeze/").status_code, 400)
        # A frozen set can still be renamed.
        response = self.client.patch(f"{SETS_URL}{occurrence_set.pk}/", {"name": "Benchmark"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.member_ids(occurrence_set), self.occurrence_ids[:2])

    def test_freeze_returns_who_froze_the_set(self):
        occurrence_set = self.create_set()
        response = self.client.post(f"{SETS_URL}{occurrence_set.pk}/freeze/")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIsNotNone(data["frozen_at"])
        self.assertEqual(data["frozen_by"]["id"], self.ml_data_manager.pk)
        self.assertNotIn("email", data["frozen_by"])
        self.assertEqual(data["user_permissions"], ["copy", "delete", "update"])

    def test_copy_makes_an_unfrozen_set_with_the_same_members(self):
        original = self.create_frozen_set()
        url = f"{SETS_URL}{original.pk}/copy/"
        response = self.client.post(url, {"name": "Benchmark v2"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(
            (data["name"], data["copied_from"], data["frozen_at"], data["occurrences_count"]),
            ("Benchmark v2", original.pk, None, 2),
        )
        self.assertEqual(self.client.post(url, {"name": "x" * 256}, format="json").status_code, 400)

    def test_list_requires_a_project_and_shows_only_its_sets(self):
        own = self.create_set()
        self.create_set(project=self.other_project)
        self.assertEqual(self.client.get(SETS_URL).status_code, 400)
        response = self.client.get(SETS_URL, {"project_id": self.project.pk})
        self.assertEqual([row["id"] for row in response.json()["results"]], [own.pk])

    def test_list_shows_member_counts_and_permissions(self):
        open_set = self.create_set()
        open_set.occurrences.add(*self.occurrence_ids[:2])
        frozen_set = self.create_frozen_set()
        response = self.client.get(SETS_URL, {"project_id": self.project.pk})
        data = response.json()
        rows = {row["id"]: row for row in data["results"]}
        self.assertEqual((rows[open_set.pk]["occurrences_count"], rows[frozen_set.pk]["occurrences_count"]), (2, 2))
        self.assertEqual(rows[open_set.pk]["user_permissions"], ["copy", "delete", "freeze", "update"])
        self.assertEqual(rows[frozen_set.pk]["user_permissions"], ["copy", "delete", "update"])
        self.assertIn("create", data["user_permissions"])

    def test_choices_list_names_and_dates_for_one_project(self):
        occurrence_set = self.create_set(name="Favourites")
        self.assertEqual(self.client.get(f"{SETS_URL}choices/").status_code, 400)
        response = self.client.get(f"{SETS_URL}choices/", {"project_id": self.project.pk})
        self.assertEqual(response.status_code, 200, response.content)
        [row] = response.json()["results"]
        self.assertEqual(
            (row["id"], row["name"], row["method"], row["populated_at"], row["frozen_at"]),
            (occurrence_set.pk, "Favourites", "manual", None, None),
        )

    def test_list_query_count_does_not_grow_with_the_number_of_sets(self):
        def count_queries(expected_rows: int):
            # Savepoints (2), project, count, rows, the user's permissions for the rows (2), and the
            # paginator's "create" permission: project and permissions again (3).
            with no_query_cache(), self.assertNumQueries(10):
                response = self.client.get(SETS_URL, {"project_id": self.project.pk})
            self.assertEqual(len(response.json()["results"]), expected_rows)

        for _ in range(3):
            self.create_set().occurrences.add(*self.occurrence_ids[:2])
        count_queries(3)
        for _ in range(3):
            self.create_frozen_set()
        count_queries(6)

    def test_choices_query_count_does_not_grow_with_the_number_of_sets(self):
        for _ in range(3):
            self.create_set()
        self.create_frozen_set()
        with no_query_cache(), self.assertNumQueries(10):
            response = self.client.get(f"{SETS_URL}choices/", {"project_id": self.project.pk})
        self.assertEqual(len(response.json()["results"]), 4)

    def test_add_query_count_does_not_grow_with_the_number_of_occurrences(self):
        occurrence_set = self.create_set()
        # Savepoints (4: request and model transaction), the set, permissions (2), one id check,
        # the row lock, the updated_at save, one insert, and the count.
        with no_query_cache(), self.assertNumQueries(12):
            response = self.client.post(
                f"{SETS_URL}{occurrence_set.pk}/add/", {"occurrence_ids": self.occurrence_ids}, format="json"
            )
        self.assertEqual(response.json()["occurrences_count"], len(self.occurrence_ids))


class TestOccurrenceSetFilter(OccurrenceSetTestCase):
    def test_occurrence_list_includes_or_excludes_the_members(self):
        occurrence_set = self.create_set()
        occurrence_set.occurrences.add(*self.occurrence_ids[:3])
        other_set = self.create_set()
        other_set.occurrences.add(*self.occurrence_ids[2:5])
        self.assertEqual(self.list_occurrence_ids({"occurrence_set_id": occurrence_set.pk}), self.occurrence_ids[:3])
        self.assertEqual(
            self.list_occurrence_ids({"not_occurrence_set_id": occurrence_set.pk}), self.occurrence_ids[3:]
        )
        self.assertEqual(
            self.list_occurrence_ids({"occurrence_set_id": occurrence_set.pk, "not_occurrence_set_id": other_set.pk}),
            self.occurrence_ids[:2],
        )

    def test_invalid_occurrence_set_id_is_refused(self):
        self.client.force_authenticate(self.superuser)
        for param in ("occurrence_set_id", "not_occurrence_set_id"):
            for value in ("abc", "0"):
                with self.subTest(param=param, value=value):
                    response = self.client.get(OCCURRENCES_URL, {"project_id": self.project.pk, param: value})
                    self.assertEqual(response.status_code, 400, response.content)


class TestOccurrenceSetPermissions(OccurrenceSetTestCase):
    """Who can read and curate occurrence sets: ML data managers and project managers curate them."""

    def attempt_each_action(self, user: User | None) -> dict[str, int]:
        occurrence_set = self.create_set()
        occurrence_set.occurrences.add(self.occurrence_ids[0])
        to_freeze = self.create_set()
        if user:
            self.client.force_authenticate(user)
        ids = {"occurrence_ids": self.occurrence_ids[:2]}
        url = f"{SETS_URL}{occurrence_set.pk}/"
        requests = {
            "list": lambda: self.client.get(SETS_URL, {"project_id": self.project.pk}),
            "retrieve": lambda: self.client.get(url),
            "create": lambda: self.client.post(SETS_URL, {"name": "New", "project": self.project.pk}, format="json"),
            "update": lambda: self.client.patch(url, {"name": "Renamed"}, format="json"),
            "add": lambda: self.client.post(f"{url}add/", ids, format="json"),
            "remove": lambda: self.client.post(f"{url}remove/", ids, format="json"),
            "copy": lambda: self.client.post(f"{url}copy/", {}, format="json"),
            "freeze": lambda: self.client.post(f"{SETS_URL}{to_freeze.pk}/freeze/"),
            "delete": lambda: self.client.delete(url),
        }
        return {name: request().status_code for name, request in requests.items()}

    writes = ("create", "update", "add", "remove", "copy", "freeze", "delete")
    curators = {
        "list": 200,
        "retrieve": 200,
        "create": 201,
        "update": 200,
        "add": 200,
        "remove": 200,
        "copy": 201,
        "freeze": 200,
        "delete": 204,
    }
    readers = {**curators, **{action: 403 for action in writes}}

    def test_superuser(self):
        self.assertEqual(self.attempt_each_action(self.superuser), self.curators)

    def test_ml_data_manager(self):
        self.assertEqual(self.attempt_each_action(self.ml_data_manager), self.curators)

    def test_project_manager(self):
        self.assertEqual(self.attempt_each_action(self.project_manager), self.curators)

    def test_basic_member(self):
        self.assertEqual(self.attempt_each_action(self.basic_member), self.readers)

    def test_non_member(self):
        self.assertEqual(self.attempt_each_action(self.non_member), self.readers)

    def test_anonymous(self):
        self.assertEqual(self.attempt_each_action(None), {**self.curators, **{action: 401 for action in self.writes}})

    def test_draft_project_sets_are_hidden_from_non_members(self):
        Project.objects.filter(pk=self.project.pk).update(draft=True)
        occurrence_set = self.create_set()
        self.client.force_authenticate(self.non_member)
        response = self.client.get(SETS_URL, {"project_id": self.project.pk})
        self.assertEqual(response.json()["results"], [])
        self.assertEqual(self.client.get(f"{SETS_URL}{occurrence_set.pk}/").status_code, 404)
        self.client.force_authenticate(self.basic_member)
        self.assertEqual(self.client.get(f"{SETS_URL}{occurrence_set.pk}/").status_code, 200)
