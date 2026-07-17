"""
Tests for the bulk identifications endpoint.

The endpoint lets an identifier apply determinations to many occurrences in one
request. The tests here pin the parts of that contract that are easy to break
without noticing: per-occurrence permission enforcement, the withdraw-previous
and determination-recompute side effects that live in ``Identification.save()``,
and the fact that validation cost must not grow with the size of the batch.
"""

import logging
from unittest import mock

from django.db import IntegrityError, connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from ami.main.api.serializers import MAX_BULK_IDENTIFICATIONS
from ami.main.models import Identification, Occurrence, Taxon
from ami.tests.fixtures.main import create_captures, create_occurrences, create_taxa, setup_test_project
from ami.users.models import User
from ami.users.roles import BasicMember, Identifier, ProjectManager

logger = logging.getLogger(__name__)

ENDPOINT = "/api/v2/identifications/bulk/"


class BulkIdentificationTestCase(APITestCase):
    """Shared fixture: one project with several occurrences and a user per role."""

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        create_taxa(project=self.project)
        create_captures(deployment=self.deployment)
        create_occurrences(deployment=self.deployment, num=4)

        self.identifier = User.objects.create_user(email="identifier@insectai.org")  # type: ignore[attr-defined]
        self.basic_member = User.objects.create_user(email="basic@insectai.org")  # type: ignore[attr-defined]
        self.non_member = User.objects.create_user(email="stranger@insectai.org")  # type: ignore[attr-defined]
        self.superuser = User.objects.create_user(  # type: ignore[attr-defined]
            email="super@insectai.org", is_staff=True, is_superuser=True
        )
        Identifier.assign_user(self.identifier, self.project)
        BasicMember.assign_user(self.basic_member, self.project)
        ProjectManager.assign_user(self.superuser, self.project)

        self.occurrences = list(Occurrence.objects.filter(project=self.project).exclude(determination=None))
        assert len(self.occurrences) >= 4, "Fixture must provide enough occurrences to catch per-row query growth"

        self.taxon = Taxon.objects.exclude(pk=self.occurrences[0].determination_id).first()
        assert self.taxon is not None

        return super().setUp()

    def post_bulk(self, items: list[dict], user: User | None = None):
        if user is not None:
            self.client.force_authenticate(user=user)
        return self.client.post(ENDPOINT, {"identifications": items}, format="json")

    def item(self, occurrence: Occurrence, taxon: Taxon | None = None, **extra) -> dict:
        return {"occurrence_id": occurrence.pk, "taxon_id": (taxon or self.taxon).pk, **extra}


class TestBulkIdentificationSuccess(BulkIdentificationTestCase):
    def test_creates_one_identification_per_item_and_updates_determinations(self):
        """The happy path: every item becomes an Identification and moves its occurrence's determination."""
        targets = self.occurrences[:3]
        response = self.post_bulk([self.item(occurrence) for occurrence in targets], user=self.identifier)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        body = response.json()
        self.assertEqual(body["created_count"], 3)
        self.assertEqual(body["error_count"], 0)
        self.assertEqual([result["status"] for result in body["results"]], ["created"] * 3)

        for occurrence in targets:
            occurrence.refresh_from_db()
            self.assertEqual(occurrence.determination, self.taxon)
            self.assertEqual(
                Identification.objects.filter(occurrence=occurrence, user=self.identifier, withdrawn=False).count(),
                1,
            )

    def test_results_are_returned_in_request_order(self):
        """Clients match results to submitted items by index, so order and index must be stable."""
        targets = self.occurrences[:3]
        response = self.post_bulk([self.item(occurrence) for occurrence in targets], user=self.identifier)

        body = response.json()
        self.assertEqual([result["index"] for result in body["results"]], [0, 1, 2])
        self.assertEqual(
            [result["occurrence_id"] for result in body["results"]],
            [occurrence.pk for occurrence in targets],
        )

    def test_comment_is_saved(self):
        response = self.post_bulk(
            [self.item(self.occurrences[0], comment="Wing pattern matches")], user=self.identifier
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        identification = Identification.objects.get(pk=response.json()["results"][0]["id"])
        self.assertEqual(identification.comment, "Wing pattern matches")

    def test_withdraws_previous_identification_by_the_same_user(self):
        """
        A user has one active identification per occurrence.

        ``Identification.save()`` withdraws the user's earlier identifications on that
        occurrence. A test using only fresh occurrences passes whether or not the bulk
        path preserves that, so this pins it with a pre-existing identification.
        """
        occurrence = self.occurrences[0]
        previous = Identification.objects.create(occurrence=occurrence, taxon=self.taxon, user=self.identifier)
        self.assertFalse(previous.withdrawn)

        other_taxon = Taxon.objects.exclude(pk__in=[self.taxon.pk]).first()
        assert other_taxon is not None
        response = self.post_bulk([self.item(occurrence, taxon=other_taxon)], user=self.identifier)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        previous.refresh_from_db()
        self.assertTrue(previous.withdrawn, "The user's earlier identification must be withdrawn")
        occurrence.refresh_from_db()
        self.assertEqual(occurrence.determination, other_taxon)

    def test_does_not_withdraw_identifications_by_other_users(self):
        """Withdrawing is scoped to the submitting user; another identifier's opinion must survive."""
        occurrence = self.occurrences[0]
        other_user_id = Identification.objects.create(occurrence=occurrence, taxon=self.taxon, user=self.superuser)

        self.post_bulk([self.item(occurrence)], user=self.identifier)

        other_user_id.refresh_from_db()
        self.assertFalse(other_user_id.withdrawn)

    def test_agreeing_with_the_current_determination_raises_the_score_to_the_human_score(self):
        """
        Agreeing with an occurrence's existing determination keeps the taxon and lifts
        the score to the human identification's score of 1.0.

        This mirrors what a single POST to /identifications/ already does, which is the
        behaviour that matters: the bulk endpoint is a faster way to do the same thing,
        not a different thing. `determination_score` feeds the project's score-threshold
        filters, so a bulk path that left the machine score in place would quietly change
        which occurrences appear in a filtered list.
        """
        occurrence = self.occurrences[0]
        original_taxon = occurrence.determination
        self.assertEqual(occurrence.determination_score, 0.9)

        response = self.post_bulk(
            [self.item(occurrence, taxon=original_taxon, agreed_with_prediction_id=occurrence.best_prediction.pk)],
            user=self.identifier,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        occurrence.refresh_from_db()
        self.assertEqual(occurrence.determination, original_taxon)
        self.assertEqual(occurrence.determination_score, 1.0)

    def test_bulk_and_single_post_leave_an_occurrence_in_the_same_state(self):
        """
        The bulk endpoint must be indistinguishable from the single-item endpoint.

        Anything the bulk path reimplements or skips — withdrawing the user's previous
        identification, recomputing the determination, the resulting score — shows up
        here as a divergence, without this test having to name each rule.
        """
        via_single, via_bulk = self.occurrences[0], self.occurrences[1]

        # Seed both with an earlier identification by the same user, so that
        # withdraw-previous is part of what the two paths have to agree on.
        other_taxon = Taxon.objects.exclude(pk=self.taxon.pk).first()
        assert other_taxon is not None
        for occurrence in (via_single, via_bulk):
            Identification.objects.create(occurrence=occurrence, taxon=other_taxon, user=self.identifier)

        self.client.force_authenticate(user=self.identifier)
        single_response = self.client.post(
            "/api/v2/identifications/",
            {"occurrence_id": via_single.pk, "taxon_id": self.taxon.pk, "comment": "same"},
            format="json",
        )
        self.assertEqual(single_response.status_code, status.HTTP_201_CREATED, single_response.content)

        bulk_response = self.post_bulk([self.item(via_bulk, comment="same")], user=self.identifier)
        self.assertEqual(bulk_response.status_code, status.HTTP_200_OK, bulk_response.content)

        via_single.refresh_from_db()
        via_bulk.refresh_from_db()
        self.assertEqual(via_bulk.determination_id, via_single.determination_id)
        self.assertEqual(via_bulk.determination_score, via_single.determination_score)

        def identification_state(occurrence):
            return sorted(
                Identification.objects.filter(occurrence=occurrence).values_list("taxon_id", "withdrawn", "comment")
            )

        self.assertEqual(identification_state(via_bulk), identification_state(via_single))

    def test_agreed_with_prediction_is_recorded(self):
        """The agree provenance FK is stored so exports can report what the user agreed with."""
        occurrence = self.occurrences[0]
        prediction = occurrence.best_prediction
        response = self.post_bulk(
            [self.item(occurrence, taxon=occurrence.determination, agreed_with_prediction_id=prediction.pk)],
            user=self.identifier,
        )

        identification = Identification.objects.get(pk=response.json()["results"][0]["id"])
        self.assertEqual(identification.agreed_with_prediction_id, prediction.pk)


class TestBulkIdentificationPartialFailure(BulkIdentificationTestCase):
    def test_valid_items_are_saved_when_one_item_fails(self):
        """
        One bad item must not discard the rest of the batch.

        Mass identification is the point of this endpoint; failing 49 good rows because
        a 50th occurrence was deleted mid-session would be worse than the N-request
        version it replaces.
        """
        items = [
            self.item(self.occurrences[0]),
            {"occurrence_id": 9_999_999, "taxon_id": self.taxon.pk},
            self.item(self.occurrences[1]),
        ]
        response = self.post_bulk(items, user=self.identifier)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        body = response.json()
        self.assertEqual(body["created_count"], 2)
        self.assertEqual(body["error_count"], 1)
        self.assertEqual([result["status"] for result in body["results"]], ["created", "error", "created"])
        self.assertIn("occurrence_id", body["results"][1]["errors"])

        for occurrence in self.occurrences[:2]:
            occurrence.refresh_from_db()
            self.assertEqual(occurrence.determination, self.taxon)

    def test_unknown_taxon_is_reported_per_item(self):
        items = [self.item(self.occurrences[0]), {"occurrence_id": self.occurrences[1].pk, "taxon_id": 9_999_999}]
        response = self.post_bulk(items, user=self.identifier)

        body = response.json()
        self.assertEqual(body["created_count"], 1)
        self.assertIn("taxon_id", body["results"][1]["errors"])

    def test_agreed_with_identification_from_another_occurrence_is_rejected(self):
        """Agree provenance must point at the occurrence being identified, not an unrelated one."""
        foreign = Identification.objects.create(occurrence=self.occurrences[1], taxon=self.taxon, user=self.superuser)
        response = self.post_bulk(
            [self.item(self.occurrences[0], agreed_with_identification_id=foreign.pk)],
            user=self.identifier,
        )

        body = response.json()
        self.assertEqual(body["created_count"], 0)
        self.assertIn("agreed_with_identification_id", body["results"][0]["errors"])

    def test_a_failed_item_does_not_roll_back_successful_items(self):
        """A rejected item must not undo the identifications already made in the batch."""
        items = [self.item(self.occurrences[0]), {"occurrence_id": self.occurrences[1].pk, "taxon_id": 9_999_999}]
        self.post_bulk(items, user=self.identifier)

        self.assertTrue(Identification.objects.filter(occurrence=self.occurrences[0]).exists())
        self.assertFalse(Identification.objects.filter(occurrence=self.occurrences[1]).exists())

    def test_a_database_failure_on_one_item_is_reported_without_losing_the_others(self):
        """
        A write that fails inside save() costs that item only.

        The request runs in a single transaction (ATOMIC_REQUESTS), so each item is
        saved inside a savepoint and its failure is caught. Without that, the first
        failure would abort the transaction, discard every identification already
        made in the request, and return a 500 instead of a per-item error. This is
        the case that made the endpoint's partial-success promise real, so it is
        pinned by forcing a failure rather than by trusting the arrangement.
        """
        failing_occurrence_id = self.occurrences[1].pk
        original_save = Identification.save

        def save_but_fail_for_one(identification_self, *args, **kwargs):
            if identification_self.occurrence_id == failing_occurrence_id:
                raise IntegrityError("simulated conflict while saving")
            return original_save(identification_self, *args, **kwargs)

        items = [self.item(occurrence) for occurrence in self.occurrences[:3]]
        with mock.patch.object(Identification, "save", save_but_fail_for_one):
            response = self.post_bulk(items, user=self.identifier)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        body = response.json()
        self.assertEqual(body["created_count"], 2)
        self.assertEqual(body["error_count"], 1)
        self.assertEqual([result["status"] for result in body["results"]], ["created", "error", "created"])

        # The surviving items are really committed, not merely reported as created.
        self.assertTrue(Identification.objects.filter(occurrence=self.occurrences[0]).exists())
        self.assertFalse(Identification.objects.filter(occurrence=self.occurrences[1]).exists())
        self.assertTrue(Identification.objects.filter(occurrence=self.occurrences[2]).exists())

    def test_every_occurrence_missing_is_reported_per_item(self):
        """
        A batch where nothing resolves answers like any other batch of failures.

        A batch of one deleted occurrence and a batch where only some are deleted are
        the same kind of failure, so they must not return different shapes.
        """
        response = self.post_bulk([{"occurrence_id": 9_999_998, "taxon_id": self.taxon.pk}], user=self.identifier)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        body = response.json()
        self.assertEqual(body["created_count"], 0)
        self.assertEqual(body["error_count"], 1)
        self.assertIn("occurrence_id", body["results"][0]["errors"])

    def test_unknown_agreement_targets_are_reported_per_item(self):
        response = self.post_bulk(
            [
                self.item(self.occurrences[0], agreed_with_identification_id=9_999_999),
                self.item(self.occurrences[1], agreed_with_prediction_id=9_999_999),
            ],
            user=self.identifier,
        )

        body = response.json()
        self.assertEqual(body["created_count"], 0)
        self.assertIn("agreed_with_identification_id", body["results"][0]["errors"])
        self.assertIn("agreed_with_prediction_id", body["results"][1]["errors"])

    def test_agreed_with_prediction_from_another_occurrence_is_rejected(self):
        foreign_prediction = self.occurrences[1].best_prediction
        response = self.post_bulk(
            [self.item(self.occurrences[0], agreed_with_prediction_id=foreign_prediction.pk)],
            user=self.identifier,
        )

        body = response.json()
        self.assertEqual(body["created_count"], 0)
        self.assertIn("agreed_with_prediction_id", body["results"][0]["errors"])

    def test_a_missing_occurrence_does_not_produce_a_spurious_agreement_error(self):
        """
        With no occurrence to compare against, the agreement target cannot be
        cross-checked, so the item reports the missing occurrence and nothing else.

        The target here is real, so the only error that could appear alongside would
        be an unwarranted "not the same occurrence" complaint.
        """
        real_target = Identification.objects.create(
            occurrence=self.occurrences[1], taxon=self.taxon, user=self.superuser
        )
        response = self.post_bulk(
            [{"occurrence_id": 9_999_997, "taxon_id": self.taxon.pk, "agreed_with_identification_id": real_target.pk}],
            user=self.identifier,
        )

        errors = response.json()["results"][0]["errors"]
        self.assertEqual(list(errors), ["occurrence_id"])

    def test_an_item_reports_every_problem_it_has(self):
        """Errors are reported per field, so one item with two problems names both."""
        response = self.post_bulk(
            [{"occurrence_id": 9_999_997, "taxon_id": 9_999_996}],
            user=self.identifier,
        )

        errors = response.json()["results"][0]["errors"]
        self.assertIn("occurrence_id", errors)
        self.assertIn("taxon_id", errors)


class TestBulkIdentificationValidation(BulkIdentificationTestCase):
    def test_empty_batch_is_rejected(self):
        response = self.post_bulk([], user=self.identifier)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_identifications_key_is_rejected(self):
        self.client.force_authenticate(user=self.identifier)
        response = self.client.post(ENDPOINT, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_integer_occurrence_id_returns_400_not_500(self):
        self.client.force_authenticate(user=self.identifier)
        response = self.client.post(
            ENDPOINT, {"identifications": [{"occurrence_id": "abc", "taxon_id": self.taxon.pk}]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_larger_than_the_cap_is_rejected(self):
        """
        The cap is what fails an oversized batch, not some other rule.

        Repeating one occurrence 201 times would be rejected by the duplicate check
        instead, and unknown IDs would be reported per item, so both would pass this
        test with the cap removed. Distinct IDs plus an assertion on the message pin
        the cap itself.
        """
        items = [
            {"occurrence_id": 9_000_000 + offset, "taxon_id": self.taxon.pk}
            for offset in range(MAX_BULK_IDENTIFICATIONS + 1)
        ]
        response = self.post_bulk(items, user=self.identifier)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(str(MAX_BULK_IDENTIFICATIONS), str(response.json()))

    def test_a_batch_at_the_cap_is_accepted(self):
        """The cap rejects what is over it, not what is exactly at it."""
        items = [
            {"occurrence_id": 9_000_000 + offset, "taxon_id": self.taxon.pk}
            for offset in range(MAX_BULK_IDENTIFICATIONS)
        ]
        response = self.post_bulk(items, user=self.identifier)

        # Every occurrence is unknown, so each is reported as an error rather than
        # the request being rejected outright.
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.json()["error_count"], MAX_BULK_IDENTIFICATIONS)

    def test_duplicate_occurrence_ids_are_rejected(self):
        """
        Two identifications for one occurrence in a single batch have no defined outcome.

        Which one wins would depend on insert-order tiebreaks rather than on anything the
        client asked for, so the batch is rejected instead.
        """
        response = self.post_bulk(
            [self.item(self.occurrences[0]), self.item(self.occurrences[0])], user=self.identifier
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_spanning_two_projects_is_rejected(self):
        """A batch is authorized against a single project, so it must not span projects."""
        other_project, other_deployment = setup_test_project(reuse=False)
        create_taxa(project=other_project)
        create_captures(deployment=other_deployment)
        create_occurrences(deployment=other_deployment, num=1)
        Identifier.assign_user(self.identifier, other_project)
        other_occurrence = Occurrence.objects.filter(project=other_project).exclude(determination=None).first()
        assert other_occurrence is not None

        response = self.post_bulk([self.item(self.occurrences[0]), self.item(other_occurrence)], user=self.identifier)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_withdrawn_cannot_be_set_through_the_bulk_endpoint(self):
        """`withdrawn` is managed by the model; accepting it from a client would corrupt the invariant."""
        response = self.post_bulk([self.item(self.occurrences[0], withdrawn=True)], user=self.identifier)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        identification = Identification.objects.get(pk=response.json()["results"][0]["id"])
        self.assertFalse(identification.withdrawn)


class TestBulkIdentificationPermissions(BulkIdentificationTestCase):
    """
    The permission matrix.

    A `detail=False` action is never routed through `has_object_permission`, so the
    endpoint has to run the check itself. These cases fail loudly if it stops doing so.
    """

    def test_identifier_can_create(self):
        response = self.post_bulk([self.item(self.occurrences[0])], user=self.identifier)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

    def test_project_manager_can_create(self):
        manager = User.objects.create_user(email="manager@insectai.org")  # type: ignore[attr-defined]
        ProjectManager.assign_user(manager, self.project)
        response = self.post_bulk([self.item(self.occurrences[0])], user=manager)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

    def test_superuser_can_create(self):
        response = self.post_bulk([self.item(self.occurrences[0])], user=self.superuser)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

    def test_basic_member_is_forbidden(self):
        """A project member without the identifier role must not be able to identify."""
        response = self.post_bulk([self.item(self.occurrences[0])], user=self.basic_member)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Identification.objects.filter(user=self.basic_member).exists())

    def test_non_member_is_forbidden(self):
        response = self.post_bulk([self.item(self.occurrences[0])], user=self.non_member)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Identification.objects.filter(user=self.non_member).exists())

    def test_anonymous_is_rejected(self):
        response = self.client.post(ENDPOINT, {"identifications": [self.item(self.occurrences[0])]}, format="json")
        self.assertIn(
            response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN), response.content
        )
        self.assertFalse(Identification.objects.exists())

    def test_permission_is_denied_for_the_whole_batch(self):
        """An unauthorized batch writes nothing at all, not a partial prefix."""
        items = [self.item(occurrence) for occurrence in self.occurrences[:3]]
        self.post_bulk(items, user=self.non_member)
        self.assertFalse(Identification.objects.exists())


class TestBulkIdentificationQueryCount(BulkIdentificationTestCase):
    """
    Query cost must stay linear in the batch, with a small and stable per-item slope.

    Asserting one exact number for one batch size cannot distinguish fixed cost from
    per-item cost, so it cannot catch an N+1 hidden in validation or in the response.
    Measuring two batch sizes and comparing the slope can.
    """

    def measure(self, size: int) -> int:
        # A fresh project per measurement keeps the two runs independent.
        project, deployment = setup_test_project(reuse=False)
        create_taxa(project=project)
        create_captures(deployment=deployment)
        create_occurrences(deployment=deployment, num=size)
        Identifier.assign_user(self.identifier, project)
        occurrences = list(Occurrence.objects.filter(project=project).exclude(determination=None))[:size]
        taxon = Taxon.objects.exclude(pk=occurrences[0].determination_id).first()
        assert taxon is not None
        items = [{"occurrence_id": occurrence.pk, "taxon_id": taxon.pk} for occurrence in occurrences]

        self.client.force_authenticate(user=self.identifier)
        with CaptureQueriesContext(connection) as captured:
            response = self.client.post(ENDPOINT, {"identifications": items}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.json()["created_count"], size)
        return len(captured.captured_queries)

    def test_per_item_query_cost_stays_within_budget(self):
        """
        Each extra identification in a batch costs a bounded number of queries.

        Measured at the time of writing: 8 queries per item, all of them inside
        `Identification.save()` (withdraw previous, insert, then
        `update_occurrence_determination` reading the current determination,
        `best_identification` and `best_prediction` before saving the occurrence).
        Resolving occurrences and taxa is batched and costs 2 queries for the whole
        request, so it does not appear in this slope.

        The budget is the measured cost, so any new per-item query fails this test.
        If a change to the write path legitimately adds one, update the number here
        deliberately rather than widening the budget to accommodate it.
        """
        small, large = 2, 6
        queries_small = self.measure(small)
        queries_large = self.measure(large)

        slope = (queries_large - queries_small) / (large - small)
        self.assertLessEqual(
            slope,
            8,
            f"Each identification should cost a bounded number of queries, measured {slope:.1f} "
            f"({queries_small} queries for {small} items, {queries_large} for {large}). "
            f"A jump here usually means something started querying per item.",
        )
