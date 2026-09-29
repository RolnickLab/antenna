import io
import json
import logging
import pathlib
import random
import tempfile

import numpy as np
import pydantic
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from ami.main.management.commands.evaluate_tracking import expand_sweep
from ami.main.models import Classification, Detection, Event, Occurrence, Taxon
from ami.main.models_future.embeddings import vectors_for_detections
from ami.ml.models.algorithm import Algorithm
from ami.ml.post_processing.registry import staff_only_config_fields
from ami.ml.post_processing.tracking_evaluation import evaluate_tracks, format_sweep_markdown, summarise_session
from ami.ml.post_processing.tracking_task import (
    DEFAULT_LINK_OPTIONS,
    AmbiguousSpeciesLabels,
    LinkOptions,
    PairTerms,
    TopLabel,
    TrackingConfig,
    TrackingTask,
    activity_multiplier,
    appearance_term,
    choose_links,
    event_transition_pairs,
    image_diagonal,
    labels_conflict,
    links_from_transition_pairs,
    pair_terms,
    propose_event_links,
    resolve_feature_algorithm,
    resolve_label_algorithm,
    shift_in_box_sizes,
    top_labels,
    total_cost,
    weighted_cost,
)
from ami.tests.fixtures.main import create_taxa, setup_test_project
from ami.tests.fixtures.tracking import create_tracking_session

logger = logging.getLogger(__name__)


def _box(x: float, y: float, size: float = 40) -> list[float]:
    return [x, y, x + size, y + size]


class TestCostTerms(SimpleTestCase):
    def test_default_weights_give_exactly_the_plain_cost(self):
        rng = random.Random(7)
        for _ in range(200):
            b1 = _box(rng.uniform(0, 500), rng.uniform(0, 500), rng.uniform(10, 90))
            b2 = _box(rng.uniform(0, 500), rng.uniform(0, 500), rng.uniform(10, 90))
            f1 = [rng.random() for _ in range(16)] if rng.random() > 0.2 else None
            f2 = [rng.random() for _ in range(16)]
            self.assertEqual(weighted_cost(pair_terms(f1, f2, b1, b2, 800)), total_cost(f1, f2, b1, b2, 800))

    def test_weights_scale_their_own_term(self):
        terms = PairTerms(appearance=0.1, iou=0.5, size_ratio=0.8, distance=0.05)
        base = weighted_cost(terms)
        self.assertAlmostEqual(weighted_cost(terms, LinkOptions(appearance_weight=3.0)), base + 0.2)
        self.assertAlmostEqual(weighted_cost(terms, LinkOptions(iou_weight=0.0)), base - 0.5)
        self.assertAlmostEqual(weighted_cost(terms, LinkOptions(distance_weight=2.0)), base + 0.05)

    def test_activity_multiplier_grows_only_past_the_reference_count(self):
        log = LinkOptions(activity_scaling="log", activity_reference_count=5)
        self.assertEqual(activity_multiplier(50, DEFAULT_LINK_OPTIONS), 1.0)
        self.assertEqual(activity_multiplier(3, log), 1.0)
        self.assertEqual(activity_multiplier(5, log), 1.0)
        self.assertGreater(activity_multiplier(50, log), activity_multiplier(20, log))
        self.assertGreater(activity_multiplier(20, log), 1.0)

        steps = LinkOptions(activity_scaling="steps", activity_steps=((10, 1.5), (30, 3.0)))
        self.assertEqual([activity_multiplier(n, steps) for n in (9, 10, 29, 30, 100)], [1.0, 1.5, 1.5, 3.0, 3.0])

    def test_labels_conflict_only_for_confident_unrelated_taxa(self):
        genus = TopLabel(taxon_id=1, score=0.9)
        species = TopLabel(taxon_id=2, score=0.9, ancestor_ids=frozenset({1}))
        other = TopLabel(taxon_id=3, score=0.9, ancestor_ids=frozenset({4}))
        unsure = TopLabel(taxon_id=3, score=0.2)
        self.assertTrue(labels_conflict(species, other, 0.5))
        self.assertFalse(labels_conflict(genus, species, 0.5), "A genus and its species are the same insect")
        self.assertFalse(labels_conflict(species, species, 0.5))
        self.assertFalse(labels_conflict(species, unsure, 0.5), "A low score is not evidence")
        self.assertFalse(labels_conflict(species, None, 0.5))


class TestChooseLinks(SimpleTestCase):
    # Detection 1 sits still but its crop looks different; detection 2 flew in and looks the same.
    STILL = PairTerms(appearance=0.18, iou=0.95, size_ratio=1.0, distance=0.002)
    MOVED = PairTerms(appearance=0.0, iou=0.3, size_ratio=0.95, distance=0.02)

    def test_defaults_take_the_lowest_cost_one_link_per_detection(self):
        pairs = [(1, 10, self.STILL), (2, 10, self.MOVED)]
        links = choose_links(pairs, cost_threshold=1.0)
        self.assertEqual([(a, b) for a, b, _ in links], [(1, 10)])
        links = choose_links([(2, 10, self.MOVED), (1, 10, self.STILL)], cost_threshold=1.0)
        self.assertEqual([(a, b) for a, b, _ in links], [(1, 10)])

    def test_stationary_pass_claims_a_still_insect_before_a_cheaper_moving_pair(self):
        still = PairTerms(appearance=0.3, iou=0.95, size_ratio=1.0, distance=0.002)
        moved = PairTerms(appearance=0.0, iou=0.7, size_ratio=1.0, distance=0.02)
        pairs = [(1, 10, still), (2, 10, moved)]
        self.assertEqual([(a, b) for a, b, _ in choose_links(pairs, cost_threshold=1.0)], [(2, 10)])
        options = LinkOptions(stationary_first=True, stationary_cost_threshold=0.5)
        self.assertEqual([(a, b) for a, b, _ in choose_links(pairs, 1.0, options=options)], [(1, 10)])
        # A still pair above the stationary threshold waits for the normal pass.
        strict = LinkOptions(stationary_first=True, stationary_cost_threshold=0.1)
        self.assertEqual([(a, b) for a, b, _ in choose_links(pairs, 1.0, options=strict)], [(2, 10)])

    def test_stationary_pass_can_link_a_still_insect_without_an_embedding(self):
        pairs = [(1, 10, PairTerms(appearance=None, iou=0.95, size_ratio=1.0, distance=0.001))]
        self.assertEqual(choose_links(pairs, 1.0, require_features=True), [])
        stationary = LinkOptions(stationary_first=True)
        self.assertEqual(choose_links(pairs, 1.0, require_features=True, options=stationary), [])
        allowed = LinkOptions(stationary_first=True, stationary_allow_missing_features=True)
        self.assertEqual(len(choose_links(pairs, 1.0, require_features=True, options=allowed)), 1)

    def test_species_gate_forbids_or_penalises_confident_disagreement(self):
        labels = {1: TopLabel(5, 0.9), 10: TopLabel(6, 0.9)}
        pairs = [(1, 10, self.STILL)]
        cost = weighted_cost(self.STILL)
        self.assertEqual(len(choose_links(pairs, 1.0, labels=labels)), 1, "The gate is off by default")
        forbid = LinkOptions(species_gate="forbid")
        self.assertEqual(choose_links(pairs, 1.0, options=forbid, labels=labels), [])
        penalty = LinkOptions(species_gate="penalty", species_gate_penalty=0.25)
        ((_, _, penalised),) = choose_links(pairs, 1.0, options=penalty, labels=labels)
        self.assertAlmostEqual(penalised, cost + 0.25)
        self.assertEqual(choose_links(pairs, cost + 0.1, options=penalty, labels=labels), [])

    def test_activity_scaling_rejects_the_same_move_on_a_crowded_sheet(self):
        moved = PairTerms(appearance=0.0, iou=0.5, size_ratio=1.0, distance=0.1)
        options = LinkOptions(activity_scaling="log", activity_reference_count=5)
        self.assertEqual(len(choose_links([(1, 10, moved)], 0.65, options=options, detection_count=4)), 1)
        self.assertEqual(choose_links([(1, 10, moved)], 0.65, options=options, detection_count=60), [])


class TestAppearanceAndMoveRules(SimpleTestCase):
    # Two boxes of side 40 whose centres are 80 px apart: no overlap, a shift of two box sizes.
    APART = dict(iou=0.0, size_ratio=1.0, distance=0.02, shift=2.0)

    def test_calibration_maps_the_similarity_range_onto_zero_to_one(self):
        options = LinkOptions(appearance_similarity_floor=0.4, appearance_similarity_ceiling=0.9)
        self.assertEqual(appearance_term(1 - 0.95, options), 0.0)
        self.assertAlmostEqual(appearance_term(1 - 0.65, options), 0.5)
        self.assertEqual(appearance_term(1 - 0.2, options), 1.0)
        self.assertEqual(appearance_term(0.123, DEFAULT_LINK_OPTIONS), 0.123)

    def test_appearance_gate_forbids_only_pairs_whose_embeddings_disagree(self):
        alike = PairTerms(appearance=0.1, iou=0.9, size_ratio=1.0, distance=0.001)
        unlike = PairTerms(appearance=0.6, iou=0.9, size_ratio=1.0, distance=0.001)
        no_vector = PairTerms(appearance=None, iou=0.9, size_ratio=1.0, distance=0.001)
        gate = LinkOptions(appearance_min_similarity=0.5)
        self.assertEqual(len(choose_links([(1, 10, unlike)], 1.0)), 1, "The gate is off by default")
        self.assertEqual(choose_links([(1, 10, unlike)], 1.0, options=gate), [])
        self.assertEqual(len(choose_links([(1, 10, alike)], 1.0, options=gate)), 1)
        self.assertEqual(len(choose_links([(1, 10, no_vector)], 1.0, require_features=False, options=gate)), 1)

    def test_move_rule_lets_a_look_alike_link_clear_of_its_old_box(self):
        alike = PairTerms(appearance=0.05, **self.APART)
        unlike = PairTerms(appearance=0.4, **self.APART)
        self.assertEqual(choose_links([(1, 10, alike)], 1.0), [], "Disjoint boxes cannot link at 1.0 by default")
        move = LinkOptions(motion_min_similarity=0.9, motion_max_shift=4.0)
        ((_, _, cost),) = choose_links([(1, 10, alike)], 1.0, options=move)
        self.assertAlmostEqual(cost, 0.05 + 0.5 + 0.02)
        self.assertEqual(choose_links([(1, 10, unlike)], 1.0, options=move), [])
        far = PairTerms(appearance=0.05, iou=0.0, size_ratio=1.0, distance=0.1, shift=8.0)
        self.assertEqual(choose_links([(1, 10, far)], 1.0, options=move), [], "The shift is capped at one overlap")
        without_vector = PairTerms(appearance=None, **self.APART)
        self.assertEqual(choose_links([(1, 10, without_vector)], 1.0, require_features=False, options=move), [])

    def test_shift_is_measured_in_box_sizes(self):
        self.assertAlmostEqual(shift_in_box_sizes(_box(0, 0, 39), _box(80, 0, 39)), 2.0)
        self.assertAlmostEqual(shift_in_box_sizes(_box(0, 0, 9), _box(0, 30, 9)), 3.0)
        self.assertEqual(pair_terms(None, None, _box(0, 0), _box(0, 0), 800).shift, 0.0)

    def test_a_malformed_box_does_not_stop_scoring(self):
        """Pairs are scored with the shift whether or not the move rule is on, so a box with no
        area, or corners the wrong way round, must score as before instead of raising."""
        for malformed in ([10, 10, 9, 20], [10, 10, 5, 20]):
            terms = pair_terms(None, None, malformed, [10, 10, 20, 20], 800)
            self.assertEqual(terms.shift, float("inf"))
            self.assertEqual(
                weighted_cost(terms), total_cost(None, None, malformed, [10, 10, 20, 20], 800), msg=malformed
            )


class TestTrackingConfigTerms(SimpleTestCase):
    def test_defaults_leave_every_new_rule_off(self):
        config = TrackingConfig(event_ids=[1])
        self.assertEqual(config.link_options(), DEFAULT_LINK_OPTIONS)

    def test_invalid_settings_are_refused(self):
        for bad in (
            {"species_gate": "sometimes"},
            {"appearance_weight": -1},
            {"species_gate_min_score": 1.5},
            {"activity_scaling": "steps"},
            {"activity_scaling": "steps", "activity_steps": [[30, 2.0], [10, 1.5]]},
            {"activity_steps": [[10, 0]]},
            {"appearance_similarity_floor": 0.9, "appearance_similarity_ceiling": 0.4},
            {"appearance_min_similarity": 1.2},
            {"motion_max_shift": 0},
        ):
            with self.subTest(bad=bad), self.assertRaises(pydantic.ValidationError):
                TrackingConfig(event_ids=[1], **bad)

    def test_new_rules_are_staff_only(self):
        config = {"species_gate": "forbid", "stationary_first": True, "appearance_weight": 2.0, "cost_threshold": 0.5}
        self.assertEqual(
            staff_only_config_fields("tracking", config), ["appearance_weight", "species_gate", "stationary_first"]
        )
        self.assertEqual(staff_only_config_fields("tracking", {"species_gate": "off"}), [])
        calibrated = {
            "appearance_similarity_floor": 0.4,
            "appearance_min_similarity": 0.5,
            "motion_min_similarity": 0.8,
        }
        self.assertEqual(staff_only_config_fields("tracking", calibrated), sorted(calibrated))


class TestSweepReporting(SimpleTestCase):
    def test_multi_detection_scores_leave_out_single_detection_tracks(self):
        truth = {1: "A", 2: "A", 3: "B", 4: "C", 5: "C"}
        times = {1: 1, 2: 2, 3: 1, 4: 1, 5: 2}
        result = evaluate_tracks(truth, {1: "x", 2: "x", 3: "y", 4: "z", 5: "w"}, times)
        self.assertEqual(result.exactly_recovered, 2, "A and the singleton B")
        self.assertEqual((result.multi_detection_exactly_recovered, result.multi_detection_tracks), (1, 2))
        self.assertEqual(result.multi_detection_mean_completeness, 0.75)
        self.assertIsNone(result.cross_species_merges)

    def test_cross_species_merges_count_tracks_joining_different_determinations(self):
        truth = {1: "A", 2: "B", 3: "C", 4: "D"}
        times = {1: 1, 2: 2, 3: 1, 4: 2}
        taxa = {"A": 10, "B": 10, "C": 10, "D": 11}
        result = evaluate_tracks(truth, {1: "x", 2: "x", 3: "y", 4: "y"}, times, taxa)
        self.assertEqual((result.merges, result.cross_species_merges), (2, 1))

    def test_session_summary_counts_occurrences_and_species_before_and_after(self):
        predictions = {1: 1, 2: 1, 3: 3, 4: 4}
        labels = {1: ("moth-a", 0.9), 2: ("moth-b", 0.4), 3: ("moth-b", 0.8)}
        summary = summarise_session(predictions, labels)
        self.assertEqual((summary["occurrences_before"], summary["occurrences_after"]), (4, 3))
        self.assertEqual((summary["unique_determinations_before"], summary["unique_determinations_after"]), (2, 2))
        self.assertEqual((summary["track_length_median"], summary["track_length_max"]), (2, 2))
        self.assertEqual(summary["multi_detection_tracks"], 1)
        merged = summarise_session({1: 1, 2: 1, 3: 1, 4: 4}, labels)
        self.assertEqual(merged["unique_determinations_after"], 1, "The track takes its best label, moth-a")

    def test_sweep_expands_a_grid_on_a_base_and_merges_object_values(self):
        settings = expand_sweep(
            {
                "base": {"require_features": False},
                "grid": {
                    "cost_threshold": [0.2, 0.4],
                    "gate": [{"species_gate": "off"}, {"species_gate": "penalty", "species_gate_penalty": 0.5}],
                },
                "configs": [{"cost_threshold": 1.0}],
            }
        )
        self.assertEqual(len(settings), 5)
        self.assertEqual(
            settings[1],
            {"require_features": False, "cost_threshold": 0.2, "species_gate": "penalty", "species_gate_penalty": 0.5},
        )
        self.assertEqual(settings[-1], {"require_features": False, "cost_threshold": 1.0})
        with self.assertRaises(CommandError):
            expand_sweep({"grid": {}, "other": 1})

    def test_markdown_shows_one_table_per_scope_and_only_the_settings_that_vary(self):
        truth, times = {1: "A", 2: "A"}, {1: 1, 2: 2}
        from ami.ml.post_processing.tracking_evaluation import sweep_row

        rows = []
        for run, threshold in ((1, 0.2), (2, 0.4)):
            evaluation = evaluate_tracks(truth, {1: "x", 2: "x"}, times, {"A": 1})
            session = summarise_session({1: 1, 2: 1}, {1: (1, 0.9)})
            settings = {"cost_threshold": threshold, "require_features": True}
            rows.append(sweep_row(run, settings, 7, evaluation, session, 1))
            rows.append(sweep_row(run, settings, "overall", evaluation, session, 1))
        markdown = format_sweep_markdown(rows)
        self.assertIn("## Session 7", markdown)
        self.assertLess(markdown.index("## Session 7"), markdown.index("## Overall"))
        self.assertIn("| run | cost_threshold | links |", markdown)
        self.assertNotIn("require_features", markdown)
        self.assertIn("| 2 | 0.4 | 1 | 1.000 | 1.000 | 1.000 |", markdown)
        # A near-perfect score must not print as perfect.
        rows[0]["link_precision"] = 0.9996
        self.assertIn("| 1 | 0.2 | 1 | 0.999 |", format_sweep_markdown(rows))


def _reference_links(event: Event, algorithm, cost_threshold: float, require_features: bool) -> set:
    """The links the tracker made before the optional cost rules existed, kept here as a frozen copy."""
    captures = list(event.captures.order_by("timestamp"))
    links = set()
    for cur, nxt in zip(captures, captures[1:]):
        if not cur.width or not cur.height:
            continue
        current, following = list(cur.detections.valid()), list(nxt.detections.valid())
        vectors = vectors_for_detections([d.pk for d in current + following], algorithm.pk) if algorithm else {}
        diag = image_diagonal(cur.width, cur.height)
        candidates = []
        for det in current:
            if vectors.get(det.pk) is None and require_features:
                continue
            for other in following:
                if vectors.get(other.pk) is None and require_features:
                    continue
                cost = total_cost(vectors.get(det.pk), vectors.get(other.pk), det.bbox, other.bbox, diag)
                if cost < cost_threshold:
                    candidates.append((cost, det.pk, other.pk))
        claimed_a, claimed_b = set(), set()
        for cost, a, b in sorted(candidates):
            if a in claimed_a or b in claimed_b:
                continue
            claimed_a.add(a)
            claimed_b.add(b)
            links.add((a, b))
    return links


class TestCostTermsOnATrackingSession(TestCase):
    """The optional rules change nothing by default, and the sweep scores what a run would do."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.project, cls.deployment = setup_test_project(reuse=False)
        cls.ground_truth = create_tracking_session(
            cls.deployment,
            taxa_list=create_taxa(cls.project),
            num_frames=10,
            num_moths=4,
            num_transient_moths=2,
            min_frames_per_moth=4,
            motion_scale=0.4,
            create_crops=False,
        )
        cls.event = Event.objects.get(pk=cls.ground_truth.event_id)

    def _algorithm(self, require_features: bool = True):
        algorithm, _, _ = resolve_feature_algorithm(
            self.event, TrackingConfig(event_ids=[self.event.pk], require_features=require_features)
        )
        return algorithm

    def test_default_settings_give_the_same_links_as_before_the_new_rules(self):
        algorithm = self._algorithm()
        for threshold, require_features in ((0.2, True), (0.6, True), (0.6, False), (1.5, False)):
            with self.subTest(threshold=threshold, require_features=require_features):
                config = TrackingConfig(
                    event_ids=[self.event.pk], cost_threshold=threshold, require_features=require_features
                )
                proposed = {(a, b) for a, b, _ in propose_event_links(self.event, algorithm, config, logger)}
                expected = _reference_links(self.event, algorithm, threshold, require_features)
                self.assertEqual(proposed, expected)
        self.assertTrue(expected, "The loosest setting links something, so the comparison is not vacuous")

    def test_precomputed_pairs_give_the_same_links_as_a_run_for_any_setting(self):
        algorithm = self._algorithm()
        transitions, _ = event_transition_pairs(self.event, algorithm)
        detection_ids = list(Detection.objects.filter(source_image__event=self.event).values_list("pk", flat=True))
        labels = top_labels(detection_ids, resolve_label_algorithm(detection_ids, None))
        for extra in (
            {},
            {"species_gate": "forbid", "species_gate_min_score": 0.0},
            {"species_gate": "penalty", "species_gate_min_score": 0.0, "species_gate_penalty": 0.3},
            {"stationary_first": True, "stationary_max_shift": 0.05, "stationary_min_iou": 0.3},
            {"activity_scaling": "log", "activity_reference_count": 1, "appearance_weight": 0.5},
            {
                "appearance_similarity_floor": 0.3,
                "appearance_similarity_ceiling": 0.9,
                "appearance_min_similarity": 0.2,
                "motion_min_similarity": 0.5,
            },
        ):
            with self.subTest(extra=extra):
                config = TrackingConfig(event_ids=[self.event.pk], cost_threshold=0.8, require_features=False, **extra)
                proposed = propose_event_links(self.event, algorithm, config, logger)
                self.assertEqual(links_from_transition_pairs(transitions, config, labels), proposed)

    def test_species_gate_blocks_links_between_differently_labelled_insects(self):
        # Every simulated insect has its own species, so a forbid gate at any score can only
        # remove links between different insects; with none of those the links are unchanged.
        config = TrackingConfig(event_ids=[self.event.pk], cost_threshold=0.8, require_features=False)
        gated = config.copy(update={"species_gate": "forbid", "species_gate_min_score": 0.0})
        plain = set(propose_event_links(self.event, None, config, logger))
        blocked = set(propose_event_links(self.event, None, gated, logger))
        self.assertTrue(blocked <= plain)
        truth = {d: insect.identifier for insect in self.ground_truth.insects for d in insect.detection_ids}
        self.assertTrue(all(truth[a] == truth[b] for a, b, _ in blocked))

    def test_species_labels_come_from_one_classifier(self):
        # A second classifier's more confident label on the same crop must not replace the
        # first one's, and with no classifier chosen the gate refuses to mix the two.
        detection_ids = list(Detection.objects.filter(source_image__event=self.event).values_list("pk", flat=True))
        first_id = resolve_label_algorithm(detection_ids, None)
        other = Algorithm.objects.create(name="Second classifier", key="second-classifier-test")
        own = Classification.objects.filter(detection_id=detection_ids[0], algorithm_id=first_id).first()
        Classification.objects.create(
            detection_id=detection_ids[0],
            algorithm=other,
            taxon=Taxon.objects.exclude(pk=own.taxon_id).first(),
            score=0.99,
            terminal=True,
            timestamp=timezone.now(),
        )
        self.assertEqual(top_labels(detection_ids, first_id)[detection_ids[0]].taxon_id, own.taxon_id)
        self.assertEqual(top_labels(detection_ids, other.pk)[detection_ids[0]].score, 0.99)
        with self.assertRaises(AmbiguousSpeciesLabels):
            resolve_label_algorithm(detection_ids, None)
        self.assertEqual(resolve_label_algorithm(detection_ids, first_id), first_id)

        gated = {"species_gate": "forbid", "species_label_algorithm_id": None}
        config = TrackingConfig(event_ids=[self.event.pk], require_features=False, **gated)
        with self.assertRaises(AmbiguousSpeciesLabels):
            propose_event_links(self.event, None, config, logger)
        TrackingTask(logger=logger, event_ids=[self.event.pk], require_features=False, **gated).run()
        self.assertEqual(Occurrence.objects.filter(event=self.event).count(), len(detection_ids))

    def _confirm_tracks(self) -> None:
        TrackingTask(logger=logger, event_ids=[self.event.pk], require_features=False, cost_threshold=0.8).run()
        Occurrence.objects.filter(event=self.event).update(grouping_verified_at=timezone.now())

    def test_sweep_writes_a_table_per_session_and_changes_nothing(self):
        self._confirm_tracks()
        before = (
            list(Detection.objects.order_by("pk").values_list("pk", "occurrence_id", "next_detection_id")),
            Occurrence.objects.count(),
            Classification.objects.count(),
        )
        sweep = {
            "base": {"require_features": False},
            "grid": {"cost_threshold": [0.0, 0.8], "species_gate": ["off", "forbid"]},
        }
        with tempfile.TemporaryDirectory() as directory:
            per_track = pathlib.Path(directory, "tracks.csv")
            output = io.StringIO()
            call_command(
                "evaluate_tracking",
                "--project",
                str(self.project.pk),
                "--sweep",
                json.dumps(sweep),
                "--output-dir",
                directory,
                "--per-track-csv",
                str(per_track),
                stdout=output,
            )
            document = json.loads(pathlib.Path(directory, "sweep.json").read_text())
            markdown = pathlib.Path(directory, "sweep.md").read_text()
            csv_lines = per_track.read_text().splitlines()

        after = (
            list(Detection.objects.order_by("pk").values_list("pk", "occurrence_id", "next_detection_id")),
            Occurrence.objects.count(),
            Classification.objects.count(),
        )
        self.assertEqual(after, before)
        self.assertEqual(len(document["runs"]), 4)
        self.assertEqual([row["scope"] for row in document["rows"]], [self.event.pk, "overall"] * 4)
        nothing, everything = document["rows"][1], document["rows"][5]
        self.assertEqual(nothing["links_proposed"], 0)
        self.assertEqual(nothing["occurrences_after"], nothing["occurrences_before"])
        self.assertEqual(everything["link_precision"], 1.0)
        self.assertEqual(everything["cross_individual_merges"], 0)
        self.assertEqual(everything["cross_species_merges"], 0)
        # Each simulated insect has its own species, so only the ungated run can join two labels.
        self.assertEqual(document["rows"][7]["links_with_conflicting_labels"], 0)
        self.assertLess(everything["occurrences_after"], everything["occurrences_before"])
        self.assertIn(f"## Session {self.event.pk}", markdown)
        self.assertIn("species_gate", markdown)
        self.assertEqual(csv_lines[0].split(",")[:3], ["run", "event_id", "kind"])
        self.assertGreater(len(csv_lines), 4)

    def test_vectors_file_replaces_the_stored_embeddings(self):
        self._confirm_tracks()
        detections = list(Detection.objects.filter(source_image__event=self.event).values_list("pk", flat=True))
        insect_of = {d: i for i, insect in enumerate(self.ground_truth.insects) for d in insect.detection_ids}
        # One direction per insect, so each insect matches only itself on appearance.
        vectors = np.eye(len(self.ground_truth.insects), 8)[[insect_of[d] for d in detections]]
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory, "vectors.npz")
            np.savez(path, detection_ids=np.array(detections), vectors=vectors)
            output = io.StringIO()
            call_command(
                "evaluate_tracking",
                "--project",
                str(self.project.pk),
                "--vectors-file",
                str(path),
                "--cost-threshold",
                "0.8",
                "--format",
                "json",
                stdout=output,
            )
        report = json.loads(output.getvalue())
        self.assertEqual(report["events"][0]["note"], "Embeddings from the vectors file.")
        self.assertEqual(report["overall"]["merges"], 0)
        self.assertGreater(report["overall"]["links_correct"], 0)
