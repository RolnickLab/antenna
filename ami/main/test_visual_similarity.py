"""Sorting the occurrence list by visual similarity (``ordering=visual_similarity``).

These pin the contract of the sort: the seed comes first and the nearest vectors next,
occurrences without a vector come last in either direction, one algorithm's vectors are
compared at a time, bad parameters are refused with 400, and the sort adds a fixed number
of queries however many rows a page has. See #1462.
"""

from unittest import mock

from cachalot.api import cachalot_disabled
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from ami.main.api.views import OccurrenceViewSet
from ami.main.models import Occurrence, Project
from ami.ml.models import Algorithm, DetectionEmbedding
from ami.tests.fixtures.main import (
    create_captures,
    create_occurrences,
    create_taxa,
    no_processing_service_http,
    setup_test_project,
)
from ami.users.models import User

SEED = [1.0, 0.0, 0.0, 0.0]
NEAR = [0.9, 0.1, 0.0, 0.0]
FAR = [0.0, 1.0, 0.0, 0.0]


class VisualSimilarityFixture(APITestCase):
    """Five occurrences: a seed, a near and a far vector from the backbone, one with a vector
    from another algorithm only, and one with no vector at all."""

    @classmethod
    def setUpTestData(cls) -> None:
        with no_processing_service_http():
            cls.project, cls.deployment = setup_test_project(reuse=False)
        cls.project.default_filters_score_threshold = 0.0
        cls.project.save()
        create_taxa(project=cls.project)
        create_captures(deployment=cls.deployment, num_nights=1, images_per_night=5)
        create_occurrences(deployment=cls.deployment, num=5, determination_score=0.9)
        cls.seed, cls.near, cls.far, cls.other_only, cls.no_vector = list(
            Occurrence.objects.filter(project=cls.project).order_by("pk")
        )
        cls.backbone = Algorithm.objects.create(name="Backbone", key="backbone", task_type="embedding")
        cls.other = Algorithm.objects.create(name="Other backbone", key="other-backbone", task_type="embedding")
        DetectionEmbedding.objects.store(
            [
                cls._embedding(cls.seed, cls.backbone, SEED),
                cls._embedding(cls.near, cls.backbone, NEAR),
                cls._embedding(cls.far, cls.backbone, FAR),
                cls._embedding(cls.other_only, cls.other, FAR),
                cls._embedding(cls.seed, cls.other, SEED),
            ]
        )
        cls.url = f"/api/v2/occurrences/?project_id={cls.project.pk}"

    @staticmethod
    def _embedding(occurrence: Occurrence, algorithm: Algorithm, vector: list[float]) -> DetectionEmbedding:
        return DetectionEmbedding(detection=occurrence.detections.get(), algorithm=algorithm, vector=vector)

    def _ids(self, query: str, expected_status: int = status.HTTP_200_OK) -> list[int]:
        response = self.client.get(f"{self.url}&{query}")
        self.assertEqual(response.status_code, expected_status, response.content)
        if expected_status != status.HTTP_200_OK:
            return []
        return [int(row["id"]) for row in response.json()["results"]]


class TestVisualSimilarityOrdering(VisualSimilarityFixture):
    def test_the_seed_comes_first_the_nearest_next_and_occurrences_without_a_vector_last(self):
        ids = self._ids(f"ordering=visual_similarity&similar_to={self.seed.pk}")
        self.assertEqual(ids[:3], [self.seed.pk, self.near.pk, self.far.pk])
        self.assertEqual(set(ids[3:]), {self.other_only.pk, self.no_vector.pk})

    def test_descending_puts_the_most_different_first_and_still_the_vector_less_last(self):
        ids = self._ids(f"ordering=-visual_similarity&similar_to={self.seed.pk}")
        self.assertEqual(ids[:3], [self.far.pk, self.near.pk, self.seed.pk])
        self.assertEqual(set(ids[3:]), {self.other_only.pk, self.no_vector.pk})

    def test_the_default_seed_is_the_most_recently_updated_occurrence_with_a_vector(self):
        """The default list is ordered by -updated_at, so the seed is its top row that has a vector."""
        self.far.save()  # Bumps updated_at.
        ids = self._ids("ordering=visual_similarity")
        self.assertEqual(ids[:3], [self.far.pk, self.near.pk, self.seed.pk])

        self.no_vector.save()  # The newest occurrence has no vector, so it is skipped as a seed.
        self.assertEqual(self._ids("ordering=visual_similarity")[0], self.far.pk)

    def test_only_one_algorithms_vectors_are_compared(self):
        """By default the algorithm with the most vectors; ``similarity_algorithm`` picks another.
        An occurrence whose only vector comes from a different algorithm counts as having none."""
        ids = self._ids(f"ordering=visual_similarity&similar_to={self.seed.pk}")
        self.assertIn(self.other_only.pk, ids[3:])

        ids = self._ids(f"ordering=visual_similarity&similar_to={self.seed.pk}&similarity_algorithm={self.other.pk}")
        self.assertEqual(ids[:2], [self.seed.pk, self.other_only.pk])
        self.assertEqual(set(ids[2:]), {self.near.pk, self.far.pk, self.no_vector.pk})

    def test_the_sort_goes_through_the_default_filters(self):
        self.project.default_filters_score_threshold = 0.95
        self.project.save()
        self.assertEqual(self._ids(f"ordering=visual_similarity&similar_to={self.seed.pk}"), [])
        self.assertEqual(len(self._ids("ordering=visual_similarity&apply_defaults=false")), 5)

    def test_bad_parameters_return_400(self):
        other_project, other_deployment = setup_test_project(reuse=False)
        create_taxa(project=other_project)
        create_captures(deployment=other_deployment, num_nights=1, images_per_night=1)
        create_occurrences(deployment=other_deployment, num=1)
        foreign = Occurrence.objects.get(project=other_project)

        for query, key in [
            ("ordering=visual_similarity&similar_to=abc", "similar_to"),
            ("ordering=visual_similarity&similar_to=0", "similar_to"),
            (f"ordering=visual_similarity&similar_to={foreign.pk}", "similar_to"),
            (f"ordering=visual_similarity&similar_to={self.no_vector.pk}", "similar_to"),
            ("ordering=visual_similarity&similarity_algorithm=abc", "similarity_algorithm"),
            (f"ordering=visual_similarity&similar_to={self.seed.pk}&similarity_algorithm=999999", "similar_to"),
        ]:
            with self.subTest(query=query):
                response = self.client.get(f"{self.url}&{query}")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
                self.assertIn(key, response.json())

    def test_a_project_without_vectors_says_so(self):
        DetectionEmbedding.objects.all().delete()
        response = self.client.get(f"{self.url}&ordering=visual_similarity")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No feature vectors", str(response.json()["ordering"]))

    def test_the_sort_adds_a_fixed_number_of_queries_however_many_rows(self):
        """The seed and algorithm lookups are a handful of queries; nothing runs per row."""

        def count(query: str) -> int:
            with CaptureQueriesContext(connection) as ctx:
                response = self.client.get(f"{self.url}&{query}")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            return len(ctx.captured_queries)

        similarity = "ordering=visual_similarity"
        # The query cache would serve repeated lookups from the first call, so it is off while
        # counting; the assertions stay outside the block so a failure cannot leave it off.
        with cachalot_disabled():
            overhead_small = count(f"{similarity}&limit=2") - count("limit=2")
            overhead_large = count(f"{similarity}&limit=5") - count("limit=5")
        self.assertEqual(overhead_small, overhead_large)
        # Project visibility, the algorithm with the most vectors, the default filters' two taxa
        # lists for the default seed, the seed itself, and its vector.
        self.assertLessEqual(overhead_large, 6)


class TestVisualSimilarityPermissions(VisualSimilarityFixture):
    """The sort shows exactly what the plain list shows for each kind of user."""

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.member = User.objects.create_user(email="similar-member@insectai.org")
        cls.project.members.add(cls.member)
        cls.non_member = User.objects.create_user(email="similar-outsider@insectai.org")
        cls.superuser = User.objects.create_superuser(email="similar-admin@insectai.org", password="x")

    def _list(self, query: str) -> tuple[int, int]:
        response = self.client.get(f"{self.url}&{query}")
        return response.status_code, response.json().get("count", 0) if response.status_code == 200 else 0

    def _assert_matches_plain_list(self):
        for name, user in [
            ("anonymous", None),
            ("non-member", self.non_member),
            ("member", self.member),
            ("superuser", self.superuser),
        ]:
            with self.subTest(user=name):
                self.client.force_authenticate(user=user)
                plain = self._list("")
                sorted_ = self._list(f"ordering=visual_similarity&similar_to={self.seed.pk}")
                self.assertEqual(sorted_[0], plain[0])
                self.assertEqual(sorted_[1], plain[1])

    def test_public_project(self):
        Project.objects.filter(pk=self.project.pk).update(draft=False)
        self.client.force_authenticate(user=None)
        self.assertEqual(self._list("")[1], 5)
        self._assert_matches_plain_list()

    def test_draft_project(self):
        Project.objects.filter(pk=self.project.pk).update(draft=True)
        self.client.force_authenticate(user=self.member)
        self.assertEqual(self._list("")[1], 5)
        self._assert_matches_plain_list()


class TestSimilarityOrderSurvivesAViewDefault(VisualSimilarityFixture):
    """A default ordering on the viewset must not replace the similarity order: the ordering filter
    drops values that are not in ``ordering_fields`` and applies the view default instead."""

    def test_the_similarity_order_wins_over_a_default_ordering(self):
        with mock.patch.object(OccurrenceViewSet, "ordering", ["-created_at"], create=True):
            ids = self._ids(f"ordering=visual_similarity&similar_to={self.seed.pk}")
            reverse = self._ids(f"ordering=-visual_similarity&similar_to={self.seed.pk}")
        self.assertEqual(ids[:3], [self.seed.pk, self.near.pk, self.far.pk])
        self.assertEqual(reverse[:3], [self.far.pk, self.near.pk, self.seed.pk])


class TestOccurrenceDetailEmbeddingAlgorithms(VisualSimilarityFixture):
    """The detail view lists the algorithms whose vector can seed a similarity sort, so the UI
    can offer the link only when it would work."""

    def _detail(self, occurrence: Occurrence) -> dict:
        response = self.client.get(f"/api/v2/occurrences/{occurrence.pk}/?project_id={self.project.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return response.json()

    def test_the_list_is_empty_without_vectors_and_names_each_algorithm_that_has_one(self):
        self.assertEqual(self._detail(self.no_vector)["embedding_algorithms"], [])
        self.assertEqual(
            self._detail(self.seed)["embedding_algorithms"],
            [{"id": self.backbone.pk, "name": "Backbone"}, {"id": self.other.pk, "name": "Other backbone"}],
        )
        self.assertEqual(
            self._detail(self.other_only)["embedding_algorithms"], [{"id": self.other.pk, "name": "Other backbone"}]
        )

    def test_the_field_costs_one_query_whatever_the_number_of_algorithms(self):
        def vector_queries(occurrence: Occurrence) -> int:
            with cachalot_disabled(), CaptureQueriesContext(connection) as queries:
                self._detail(occurrence)
            return sum("ml_detectionembedding" in query["sql"] for query in queries.captured_queries)

        self.assertEqual(vector_queries(self.no_vector), 1)
        self.assertEqual(vector_queries(self.seed), 1)

    def test_the_list_view_does_not_carry_the_field(self):
        response = self.client.get(f"{self.url}")
        self.assertNotIn("embedding_algorithms", response.json()["results"][0])
