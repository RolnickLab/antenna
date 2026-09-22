import contextlib
import csv
import io
import json
import pathlib
import tempfile

from django.test import SimpleTestCase

from ami.ml.post_processing.tracking_evaluation import evaluate_csv_files, evaluate_tracks, main, tracks_from_links

# Three confirmed tracks: A has four detections, B two, C one. B runs alongside A in time.
GROUND_TRUTH = {1: "A", 2: "A", 3: "A", 4: "A", 5: "B", 6: "B", 7: "C"}
TIMESTAMPS = {1: 1, 2: 2, 3: 3, 4: 4, 5: 1, 6: 2, 7: 3}


def _evaluate(predictions: dict, timestamps: dict | None = None):
    return evaluate_tracks(GROUND_TRUTH, predictions, timestamps or TIMESTAMPS)


class TestEvaluateTracks(SimpleTestCase):
    def test_perfect_prediction_scores_one_everywhere(self):
        result = _evaluate({1: "x", 2: "x", 3: "x", 4: "x", 5: "y", 6: "y", 7: "z"})
        self.assertEqual((result.pairwise_precision, result.pairwise_recall, result.pairwise_f1), (1.0, 1.0, 1.0))
        self.assertEqual((result.link_precision, result.link_recall), (1.0, 1.0))
        self.assertEqual((result.links_correct, result.links_ground_truth), (4, 4))
        self.assertEqual((result.exactly_recovered, result.merges, result.fragmented_tracks), (3, 0, 0))
        self.assertEqual((result.ground_truth_tracks, result.detections, result.ground_truth_singletons), (3, 7, 1))

    def test_fully_fragmented_prediction_has_no_recall_and_undefined_precision(self):
        result = _evaluate({d: f"p{d}" for d in GROUND_TRUTH})
        self.assertEqual(result.pairwise_predicted, 0)
        self.assertIsNone(result.pairwise_precision)
        self.assertEqual(result.pairwise_recall, 0.0)
        self.assertIsNone(result.link_precision)
        self.assertEqual(result.link_recall, 0.0)
        track_a = next(s for s in result.ground_truth_track_scores if s.track_id == "A")
        self.assertEqual((track_a.fragments, track_a.completeness), (4, 0.25))
        self.assertEqual(result.exactly_recovered, 1, "Only the single-detection track is recovered")

    def test_over_merged_prediction_keeps_recall_and_loses_precision(self):
        result = _evaluate({d: "all" for d in GROUND_TRUTH})
        self.assertEqual((result.pairwise_true_positives, result.pairwise_predicted), (7, 21))
        self.assertAlmostEqual(result.pairwise_precision, 1 / 3)
        self.assertEqual(result.pairwise_recall, 1.0)
        self.assertEqual(result.merges, 1)
        (merged,) = result.predicted_track_scores
        self.assertEqual((merged.ground_truth_tracks, merged.purity), (3, 4 / 7))
        # Interleaving A and B in time means no consecutive predicted pair is a true link.
        self.assertEqual((result.links_correct, result.links_predicted), (0, 6))

    def test_one_missed_link_splits_a_track_in_two(self):
        result = _evaluate({1: "x", 2: "x", 3: "w", 4: "w", 5: "y", 6: "y", 7: "z"})
        self.assertEqual((result.pairwise_precision, result.pairwise_recall), (1.0, 3 / 7))
        self.assertEqual((result.link_precision, result.link_recall), (1.0, 0.75))
        track_a = next(s for s in result.ground_truth_track_scores if s.track_id == "A")
        self.assertEqual((track_a.fragments, track_a.completeness, track_a.exactly_recovered), (2, 0.5, False))
        self.assertEqual((result.fragmented_tracks, result.merges), (1, 0))

    def test_detections_outside_confirmed_tracks_are_ignored(self):
        perfect = _evaluate({1: "x", 2: "x", 3: "x", 4: "x", 5: "y", 6: "y", 7: "z"})
        # Detection 99 sits between 1 and 2 in the predicted track; 100 joins track B's prediction.
        with_unknowns = _evaluate(
            {1: "x", 99: "x", 2: "x", 3: "x", 4: "x", 5: "y", 6: "y", 100: "y", 7: "z"},
            timestamps={**TIMESTAMPS, 99: 1.5, 100: 3},
        )
        self.assertEqual(with_unknowns.to_dict(), perfect.to_dict())

    def test_detection_missing_from_predictions_is_its_own_track(self):
        result = _evaluate({1: "x", 2: "x", 3: "x", 5: "y", 6: "y", 7: "z"})
        track_a = next(s for s in result.ground_truth_track_scores if s.track_id == "A")
        self.assertEqual((track_a.fragments, track_a.completeness), (2, 0.75))

    def test_missing_timestamp_is_an_error(self):
        with self.assertRaises(ValueError):
            evaluate_tracks(GROUND_TRUTH, {}, {1: 1})

    def test_result_serialises_to_json(self):
        result = _evaluate({d: "all" for d in GROUND_TRUTH})
        payload = json.loads(json.dumps(result.to_dict()))
        self.assertEqual(payload["merges"], 1)
        self.assertNotIn("ground_truth_track_scores", result.to_dict(include_tracks=False))


class TestTracksFromLinks(SimpleTestCase):
    def test_chains_take_the_id_of_their_first_detection(self):
        tracks = tracks_from_links([1, 2, 3, 4, 5], [(1, 2), (2, 3), (4, 5)])
        self.assertEqual(tracks, {1: 1, 2: 1, 3: 1, 4: 4, 5: 4})

    def test_unlinked_detections_are_singletons(self):
        self.assertEqual(tracks_from_links([7, 8], []), {7: 7, 8: 8})

    def test_branching_links_are_rejected(self):
        with self.assertRaises(ValueError):
            tracks_from_links([1, 2, 3], [(1, 2), (1, 3)])

    def test_cycles_are_rejected(self):
        with self.assertRaises(ValueError):
            tracks_from_links([1, 2], [(1, 2), (2, 1)])


CSV_COLUMNS = ["occurrence_id", "detection_id", "timestamp", "frame_index", "grouping_verified"]


def _write_csv(path: pathlib.Path, rows: list[tuple]) -> str:
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(rows)
    return str(path)


class TestCsvAdapter(SimpleTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = pathlib.Path(self.directory.name)
        # Occurrence 10 is confirmed; occurrence 20 is not, so its detection is not scored.
        self.ground_truth = _write_csv(
            root / "gt.csv",
            [
                (10, 1, "2026-06-01T22:00:00", 0, "true"),
                (10, 2, "2026-06-01T22:01:00", 1, "true"),
                (10, 3, "2026-06-01T22:02:00", 2, "true"),
                (20, 4, "2026-06-01T22:00:00", 0, "false"),
            ],
        )
        self.predictions = _write_csv(
            root / "pred.csv",
            [(5, 1, "", "", ""), (5, 2, "", "", ""), (6, 3, "", "", ""), (6, 4, "", "", "")],
        )

    def test_only_confirmed_rows_are_ground_truth(self):
        result = evaluate_csv_files(self.ground_truth, self.predictions)
        self.assertEqual((result.ground_truth_tracks, result.detections), (1, 3))
        self.assertEqual((result.links_correct, result.links_ground_truth), (1, 2))
        self.assertEqual(result.merges, 0)

    def test_entry_point_prints_json(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main(["--ground-truth", self.ground_truth, "--predictions", self.predictions, "--format", "json"])
        self.assertEqual(json.loads(output.getvalue())["pairwise_recall"], 1 / 3)
