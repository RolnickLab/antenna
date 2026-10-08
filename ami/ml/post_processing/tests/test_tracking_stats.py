import datetime

from django.test import SimpleTestCase

from ami.ml.post_processing.tracking import stats


class TestMotion(SimpleTestCase):
    def test_a_still_insect_has_no_motion(self):
        self.assertEqual(stats.motion([[0, 0, 10, 10]] * 3, diagonal=100.0), 0.0)

    def test_motion_is_the_mean_step_between_consecutive_centres(self):
        boxes = [[0, 0, 10, 10], [30, 0, 40, 10], [30, 40, 40, 50]]
        self.assertEqual(stats.motion(boxes, diagonal=100.0), 0.35)

    def test_path_length_is_the_total_of_the_steps(self):
        boxes = [[0, 0, 10, 10], [30, 0, 40, 10], [30, 40, 40, 50]]
        self.assertEqual(stats.path_length(boxes, diagonal=100.0), 0.7)

    def test_a_single_box_has_no_motion(self):
        self.assertEqual(stats.motion([[0, 0, 10, 10]], diagonal=100.0), 0.0)


class TestFrameDiagonal(SimpleTestCase):
    def test_uses_the_largest_capture_size(self):
        self.assertEqual(stats.frame_diagonal([(300, 100), (600, 800)], []), 1000.0)

    def test_falls_back_to_the_farthest_box_corner_without_dimensions(self):
        self.assertEqual(stats.frame_diagonal([(None, None)], [[0, 0, 30, 10], [0, 0, 10, 40]]), 50.0)

    def test_is_one_when_nothing_is_known(self):
        self.assertEqual(stats.frame_diagonal([], []), 1.0)


class TestSizeChange(SimpleTestCase):
    def test_is_largest_area_over_smallest(self):
        self.assertEqual(stats.size_change([[0, 0, 10, 10], [0, 0, 20, 20], [0, 0, 5, 20]]), 4.0)

    def test_areas_are_floored_at_one(self):
        self.assertEqual(stats.size_change([[0, 0, 0, 0], [0, 0, 10, 10]]), 100.0)

    def test_is_one_without_boxes(self):
        self.assertEqual(stats.size_change([]), 1.0)


class TestLabels(SimpleTestCase):
    def test_distinct_taxa_ignores_labels_without_a_taxon(self):
        self.assertEqual(stats.distinct_taxa([1, 2, 2, None]), 2)

    def test_agreement_is_the_share_naming_the_determination(self):
        self.assertEqual(stats.label_agreement([1, 1, 2, 3], 1), 0.5)

    def test_agreement_is_none_without_labels(self):
        self.assertIsNone(stats.label_agreement([], 1))

    def test_missing_taxa_never_agree_with_a_missing_determination(self):
        self.assertEqual(stats.label_agreement([None, 1], None), 0.0)


class TestTaxaNamed(SimpleTestCase):
    def test_counts_detections_per_taxon_and_keeps_the_best_score(self):
        labels = [
            stats.Label(1, 7, "Cydia pomonella", 0.9),
            stats.Label(1, 7, "Cydia pomonella", 0.95),
            stats.Label(2, 7, "Cydia pomonella", 0.8),
            stats.Label(2, 8, "Aroga flavicomella", 0.03),
            stats.Label(3, None, None, 0.5),
        ]
        self.assertEqual(
            stats.taxa_named(labels),
            [
                stats.TaxonLabels(
                    taxon_id=7, name="Cydia pomonella", detection_count=2, score_mean=0.8833, score_max=0.95
                ),
                stats.TaxonLabels(
                    taxon_id=8, name="Aroga flavicomella", detection_count=1, score_mean=0.03, score_max=0.03
                ),
            ],
        )

    def test_a_taxon_without_scores_has_no_best_score(self):
        taxa = stats.taxa_named([stats.Label(1, 7, "Cydia pomonella", None)])
        self.assertIsNone(taxa[0].score_max)
        self.assertIsNone(taxa[0].score_mean)


class TestScoresAndDuration(SimpleTestCase):
    def test_score_range_leaves_out_missing_scores(self):
        self.assertEqual(stats.score_range([0.2, None, 0.8, 0.5]), (0.2, 0.5, 0.8))

    def test_score_range_is_empty_without_scores(self):
        self.assertEqual(stats.score_range([None]), (None, None, None))

    def test_duration_spans_the_first_to_the_last_time(self):
        start = datetime.datetime(2026, 7, 1, 22, 0, 0)
        times = [start + datetime.timedelta(seconds=40), start, None, start + datetime.timedelta(seconds=20)]
        self.assertEqual(stats.duration_seconds(times), 40.0)

    def test_duration_needs_two_times(self):
        self.assertIsNone(stats.duration_seconds([datetime.datetime(2026, 7, 1), None]))


class TestOccurrenceFigures(SimpleTestCase):
    def test_collects_every_figure(self):
        figures = stats.occurrence_figures(
            boxes=[[0, 0, 10, 10], [30, 0, 40, 10]],
            sizes=[(600, 800), (600, 800)],
            labels=[stats.Label(1, 1, "A", 0.4), stats.Label(2, 2, "B", 0.7)],
            determination_id=2,
            timestamps=[datetime.datetime(2026, 7, 1, 22, 0, 0), datetime.datetime(2026, 7, 1, 22, 0, 20)],
        )
        self.assertEqual(
            figures,
            stats.OccurrenceFigures(
                detection_count=2,
                motion=0.03,
                path_length=0.03,
                size_change=1.0,
                distinct_taxa=2,
                label_agreement=0.5,
                taxa=[
                    stats.TaxonLabels(taxon_id=2, name="B", detection_count=1, score_mean=0.7, score_max=0.7),
                    stats.TaxonLabels(taxon_id=1, name="A", detection_count=1, score_mean=0.4, score_max=0.4),
                ],
                duration_seconds=20.0,
                score_min=0.4,
                score_mean=0.55,
                score_max=0.7,
            ),
        )
