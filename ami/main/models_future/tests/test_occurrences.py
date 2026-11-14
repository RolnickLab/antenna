import datetime

from django.test import TestCase

from ami.main.models import Deployment, Detection, Event, Project, SourceImage
from ami.main.models_future.occurrences import Occurrence
from ami.main.models_future.taxonomy import Taxon


class TestOccurrenceValidQuerySet(TestCase):
    """
    Covers OccurrenceQuerySet.valid() tightening for Issue #1310:
    excludes occurrences with no real detections and occurrences missing a
    determination, in addition to the existing detections__isnull=True
    exclusion.
    """

    def setUp(self):
        from ami.ml.models.algorithm import Algorithm

        self.project = Project.objects.create(name="Occurrence Valid Test Project")
        self.deployment = Deployment.objects.create(project=self.project, name="dep")
        self.event = Event.objects.create(
            project=self.project,
            deployment=self.deployment,
            group_by="2024-01-01",
            start=datetime.datetime(2024, 1, 1, 0, 0),
        )
        self.source_image = SourceImage.objects.create(
            deployment=self.deployment,
            project=self.project,
            event=self.event,
            path="occvalid-test.jpg",
        )
        self.algorithm = Algorithm.objects.create(name="valid-detector", key="valid-detector", task_type="detection")
        self.taxon = Taxon.objects.create(name="Occurrence Valid Test Taxon")

    def _make_occurrence_with_real_detection(self) -> Occurrence:
        occ = Occurrence.objects.create(
            project=self.project,
            event=self.event,
            deployment=self.deployment,
            determination=self.taxon,
        )
        Detection.objects.create(
            source_image=self.source_image,
            bbox=[0.0, 0.0, 1.0, 1.0],
            detection_algorithm=self.algorithm,
            occurrence=occ,
        )
        return occ

    def _make_occurrence_with_only_null_detection(self) -> Occurrence:
        occ = Occurrence.objects.create(
            project=self.project,
            event=self.event,
            deployment=self.deployment,
            determination=self.taxon,
        )
        Detection.objects.create(
            source_image=self.source_image,
            bbox=None,
            detection_algorithm=self.algorithm,
            occurrence=occ,
        )
        return occ

    def _make_occurrence_with_null_determination(self) -> Occurrence:
        occ = Occurrence.objects.create(
            project=self.project,
            event=self.event,
            deployment=self.deployment,
            determination=None,
        )
        Detection.objects.create(
            source_image=self.source_image,
            bbox=[0.0, 0.0, 1.0, 1.0],
            detection_algorithm=self.algorithm,
            occurrence=occ,
        )
        return occ

    def test_valid_returns_only_real_with_determination(self):
        real = self._make_occurrence_with_real_detection()
        null_only = self._make_occurrence_with_only_null_detection()
        no_determination = self._make_occurrence_with_null_determination()

        valid_qs = Occurrence.objects.filter(project=self.project).valid()
        valid_pks = set(valid_qs.values_list("pk", flat=True))

        self.assertIn(real.pk, valid_pks)
        self.assertNotIn(null_only.pk, valid_pks)
        self.assertNotIn(no_determination.pk, valid_pks)


class TestOccurrenceAlgorithmFilterQuerySet(TestCase):
    """
    Covers OccurrenceQuerySet.processed_by_algorithm / not_processed_by_algorithm,
    which back the ?algorithm= and ?not_algorithm= occurrence filters (PR #1368).

    The filter must match an algorithm by either role it can play: the detector that
    made a detection, or the classifier / post-processing algorithm that authored a
    classification. It must also count each occurrence once — the previous join form
    (``detections__classifications__algorithm__in``) returned one row per matching
    classification, inflating the paginator's COUNT and duplicating occurrences across
    pages.
    """

    def setUp(self):
        from ami.ml.models.algorithm import Algorithm

        self.project = Project.objects.create(name="Occurrence Algo Filter Project")
        self.deployment = Deployment.objects.create(project=self.project, name="dep")
        self.event = Event.objects.create(
            project=self.project,
            deployment=self.deployment,
            group_by="2024-01-01",
            start=datetime.datetime(2024, 1, 1, 0, 0),
        )
        self.source_image = SourceImage.objects.create(
            deployment=self.deployment,
            project=self.project,
            event=self.event,
            path="occ-algo-filter.jpg",
        )
        self.taxon = Taxon.objects.create(name="Occurrence Algo Filter Taxon")

        self.detector = Algorithm.objects.create(name="Filter Detector", version=1, task_type="localization")
        self.classifier = Algorithm.objects.create(name="Filter Classifier", version=1, task_type="classification")
        self.other = Algorithm.objects.create(name="Filter Other", version=1, task_type="classification")

        # Detected by `detector`, classified once by `classifier`.
        self.occ_classified = self._make_occurrence(detector=self.detector, classifiers=[self.classifier])
        # Same pair, but classified three times — the double-count trap.
        self.occ_multi = self._make_occurrence(
            detector=self.detector, classifiers=[self.classifier, self.classifier, self.classifier]
        )
        # A different algorithm entirely, to prove filters are exclusive.
        self.occ_other = self._make_occurrence(detector=self.other, classifiers=[self.other])

    def _make_occurrence(self, detector, classifiers) -> Occurrence:
        occ = Occurrence.objects.create(
            project=self.project,
            event=self.event,
            deployment=self.deployment,
            determination=self.taxon,
        )
        detection = Detection.objects.create(
            source_image=self.source_image,
            bbox=[0.0, 0.0, 1.0, 1.0],
            detection_algorithm=detector,
            occurrence=occ,
        )
        for classifier in classifiers:
            detection.classifications.create(
                taxon=self.taxon,
                algorithm=classifier,
                score=0.9,
                timestamp=datetime.datetime.now(),
            )
        return occ

    def _pks(self, queryset):
        return set(queryset.values_list("pk", flat=True))

    def test_filter_by_classifier_matches_its_occurrences(self):
        matched = Occurrence.objects.filter(project=self.project).processed_by_algorithm([self.classifier.pk])
        self.assertEqual(self._pks(matched), {self.occ_classified.pk, self.occ_multi.pk})

    def test_filter_by_detector_matches_occurrences_it_detected(self):
        """A detector authors no Classification, so the old classification-join form
        returned nothing for it. Matching through Detection.detection_algorithm is what
        lets the user filter by a localizer at all."""
        matched = Occurrence.objects.filter(project=self.project).processed_by_algorithm([self.detector.pk])
        self.assertEqual(self._pks(matched), {self.occ_classified.pk, self.occ_multi.pk})

    def test_count_not_inflated_by_multiple_classifications(self):
        """The occurrence with three classifications by the same algorithm must count
        once. The paginator calls this same COUNT, so an inflated value would report
        four occurrences where there are two and repeat rows across pages."""
        matched = Occurrence.objects.filter(project=self.project).processed_by_algorithm([self.classifier.pk])
        self.assertEqual(matched.count(), 2)

    def test_exclude_removes_matching_occurrences(self):
        remaining = Occurrence.objects.filter(project=self.project).not_processed_by_algorithm([self.other.pk])
        self.assertEqual(self._pks(remaining), {self.occ_classified.pk, self.occ_multi.pk})

    def test_exclude_is_the_complement_of_include(self):
        base = Occurrence.objects.filter(project=self.project)
        ids = [self.classifier.pk]
        included = self._pks(base.processed_by_algorithm(ids))
        excluded = self._pks(base.not_processed_by_algorithm(ids))
        self.assertEqual(included | excluded, self._pks(base))
        self.assertEqual(included & excluded, set())
