import datetime

from django.db import connection
from django.db.models import ForeignKey
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ami.main.models import Detection, Event, Identification, Occurrence, Project, SourceImage, Taxon
from ami.main.models_future.occurrence_merges import MERGE_RULES, merge_occurrences, refresh_determinations
from ami.ml.models import Algorithm, AlgorithmResult
from ami.tests.fixtures.main import create_taxa, setup_test_project
from ami.users.models import User


class _MergeCase(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.project, cls.deployment = setup_test_project(reuse=False)
        create_taxa(project=cls.project)
        cls.taxon, cls.other_taxon = list(Taxon.objects.filter(projects=cls.project).order_by("pk")[:2])
        cls.algorithm = Algorithm.objects.create(name="Test size filter", key="test-merge-size-filter")
        cls.user = User.objects.create_user(email="merge-identifier@insectai.org")  # type: ignore[attr-defined]
        cls.event = cls._event(datetime.datetime(2024, 6, 1, 22, 0))

    @classmethod
    def _event(cls, start: datetime.datetime) -> Event:
        return Event.objects.create(
            deployment=cls.deployment, project=cls.project, start=start, group_by=start.date().isoformat()
        )

    def _occurrence(self, detections: int = 1, event: Event | None = None, project: Project | None = None):
        event = event or self.event
        occurrence = Occurrence.objects.create(
            event=event, deployment=self.deployment, project=project or self.project
        )
        for i in range(detections):
            capture = SourceImage.objects.create(
                deployment=self.deployment,
                event=event,
                timestamp=event.start + datetime.timedelta(minutes=i),
                path=f"test/merge-{occurrence.pk}-{i}.jpg",
            )
            detection = Detection.objects.create(
                source_image=capture, timestamp=capture.timestamp, bbox=[0, 0, 10, 10], occurrence=occurrence
            )
            detection.classifications.create(taxon=self.taxon, score=0.9, timestamp=capture.timestamp)
        return occurrence

    def _result(self, occurrence: Occurrence) -> AlgorithmResult:
        return AlgorithmResult.objects.record(
            occurrence=occurrence, algorithm=self.algorithm, kind="size_filter", data={"relative_size": 0.01}
        )


class TestMergeOccurrences(_MergeCase):
    def test_everything_an_absorbed_occurrence_holds_moves_to_the_kept_one(self):
        kept, absorbed = self._occurrence(detections=2), self._occurrence(detections=3)
        own_result, moved_result = self._result(kept), self._result(absorbed)
        identification = Identification.objects.create(occurrence=absorbed, user=self.user, taxon=self.other_taxon)
        absorbed_detections = list(absorbed.detections.order_by("pk").values_list("pk", flat=True))

        merge = merge_occurrences({absorbed.pk: kept.pk})

        self.assertFalse(Occurrence.objects.filter(pk=absorbed.pk).exists())
        self.assertEqual(kept.detections.count(), 5)
        self.assertEqual(set(kept.algorithm_results.values_list("pk", flat=True)), {own_result.pk, moved_result.pk})
        identification.refresh_from_db()
        self.assertEqual(identification.occurrence_id, kept.pk)
        self.assertEqual(merge.absorbed, {kept.pk: [absorbed.pk]})
        self.assertEqual(merge.moved_detections, {kept.pk: [(pk, absorbed.pk) for pk in absorbed_detections]})
        self.assertEqual(merge.moved_identifications, {kept.pk: [(identification.pk, absorbed.pk)]})
        self.assertEqual(merge.moved_results, {kept.pk: [(moved_result.pk, absorbed.pk)]})
        self.assertEqual(merge.withdrawn_identification_ids, {})

    def test_the_determination_follows_the_moved_identification(self):
        kept, absorbed = self._occurrence(), self._occurrence()
        Identification.objects.create(occurrence=absorbed, user=self.user, taxon=self.other_taxon)

        merge_occurrences({absorbed.pk: kept.pk})

        kept.refresh_from_db()
        self.assertEqual(kept.determination_id, self.other_taxon.pk)

    def test_the_determination_is_left_to_the_caller_when_asked(self):
        kept, absorbed = self._occurrence(), self._occurrence()
        Identification.objects.create(occurrence=absorbed, user=self.user, taxon=self.other_taxon)
        Occurrence.objects.filter(pk=kept.pk).update(determination=self.taxon)

        merge_occurrences({absorbed.pk: kept.pk}, recompute_determinations=False)

        kept.refresh_from_db()
        self.assertEqual(kept.determination_id, self.taxon.pk)
        refresh_determinations(Occurrence.objects.select_related("determination").filter(pk=kept.pk))
        kept.refresh_from_db()
        self.assertEqual(kept.determination_id, self.other_taxon.pk)

    def test_a_user_keeps_only_their_newest_identification(self):
        kept, first, second = self._occurrence(), self._occurrence(), self._occurrence()
        on_kept = Identification.objects.create(occurrence=kept, user=self.user, taxon=self.taxon)
        older = Identification.objects.create(occurrence=first, user=self.user, taxon=self.taxon)
        newest = Identification.objects.create(occurrence=second, user=self.user, taxon=self.other_taxon)

        merge = merge_occurrences({first.pk: kept.pk, second.pk: kept.pk})

        active = Identification.objects.filter(occurrence=kept, withdrawn=False)
        self.assertEqual(list(active.values_list("pk", flat=True)), [newest.pk])
        self.assertEqual(sorted(merge.withdrawn_identification_ids[kept.pk]), sorted([on_kept.pk, older.pk]))

    def test_several_keepers_merge_in_one_call(self):
        kept_a, kept_b = self._occurrence(), self._occurrence()
        absorbed = [self._occurrence() for _ in range(4)]
        mapping = {absorbed[0].pk: kept_a.pk, absorbed[1].pk: kept_a.pk, absorbed[2].pk: kept_b.pk}
        mapping[absorbed[3].pk] = kept_b.pk

        merge = merge_occurrences(mapping)

        self.assertEqual(kept_a.detections.count(), 3)
        self.assertEqual(kept_b.detections.count(), 3)
        self.assertEqual(merge.absorbed, {kept_a.pk: sorted(mapping)[:2], kept_b.pk: sorted(mapping)[2:]})

    def test_the_query_count_does_not_grow_with_the_number_of_occurrences(self):
        def queries_to_merge(count: int) -> int:
            kept = self._occurrence()
            mapping = {}
            for _ in range(count):
                absorbed = self._occurrence(detections=2)
                self._result(absorbed)
                Identification.objects.create(occurrence=absorbed, user=self.user, taxon=self.taxon)
                mapping[absorbed.pk] = kept.pk
            with CaptureQueriesContext(connection) as context:
                merge_occurrences(mapping, recompute_determinations=False)
            return len(context.captured_queries)

        self.assertEqual(queries_to_merge(2), queries_to_merge(6))

    def test_an_empty_mapping_does_nothing(self):
        with self.assertNumQueries(0):
            merge = merge_occurrences({})
        self.assertEqual(merge.absorbed, {})


class TestMergeOccurrencesRefuses(_MergeCase):
    def _assert_refused(self, mapping: dict[int, int], message: str) -> None:
        before = list(Detection.objects.order_by("pk").values_list("pk", "occurrence_id"))
        occurrences = set(Occurrence.objects.values_list("pk", flat=True))
        with self.assertRaisesRegex(ValueError, message):
            merge_occurrences(mapping)
        self.assertEqual(list(Detection.objects.order_by("pk").values_list("pk", "occurrence_id")), before)
        self.assertEqual(set(Occurrence.objects.values_list("pk", flat=True)), occurrences)

    def test_occurrences_of_another_project(self):
        other_project, _ = setup_test_project(reuse=False)
        kept, absorbed = self._occurrence(), self._occurrence(project=other_project)
        self._assert_refused({absorbed.pk: kept.pk}, "another project")

    def test_occurrences_of_another_session(self):
        later = self._event(datetime.datetime(2024, 6, 2, 22, 0))
        kept, absorbed = self._occurrence(), self._occurrence(event=later)
        self._assert_refused({absorbed.pk: kept.pk}, "another session")

    def test_a_kept_occurrence_that_is_also_absorbed(self):
        a, b, c = self._occurrence(), self._occurrence(), self._occurrence()
        self._assert_refused({a.pk: b.pk, b.pk: c.pk}, "both kept and absorbed")

    def test_an_occurrence_merged_into_itself(self):
        a = self._occurrence()
        self._assert_refused({a.pk: a.pk}, "both kept and absorbed")

    def test_an_occurrence_that_does_not_exist(self):
        kept, absorbed = self._occurrence(), self._occurrence()
        missing = absorbed.pk
        absorbed.delete()
        self._assert_refused({missing: kept.pk}, "do not exist")


class TestMergeRules(TestCase):
    def test_every_link_to_an_occurrence_has_a_merge_rule(self):
        """A new table that points at occurrences must decide what a merge does with its rows."""
        links = {
            (relation.related_model._meta.label, relation.field.name)
            for relation in Occurrence._meta.related_objects
            if isinstance(relation.field, ForeignKey)
        }
        self.assertEqual(links - set(MERGE_RULES), set(), "Add a rule to MERGE_RULES in occurrence_merges.py.")
        self.assertEqual(set(MERGE_RULES) - links, set())
