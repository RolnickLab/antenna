"""Tests for the regional taxa-list service (issue #1364, Phase 1).

Covers: GBIF source-client parsing, the wide-union merge, mapping merged species to
Taxon rows, the model-coverage relationship and its refresh hook/command, and the
generate_regional_taxa_list() orchestration (idempotency, the report-only classifier
overlay, and the default-covered-only vs. include_uncovered behaviour).

Every test here uses a stubbed RegionalSpeciesSource or a monkeypatched HTTP session —
nothing exercises the network.
"""

from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from ami.main.models import Project, RegionSource, TaxaList, Taxon, TaxonRank
from ami.main.services.gbif import GBIFRegionalSource
from ami.main.services.regional_taxa import (
    LEPIDOPTERA_SCOPE,
    MergedSpecies,
    SourceSpecies,
    apply_model_coverage,
    generate_regional_taxa_list,
    map_to_taxa,
    merge_source_species,
)
from ami.ml.models.algorithm import Algorithm, AlgorithmCategoryMap


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


class _FakeGBIFSession:
    """Stub for requests.Session covering GBIFRegionalSource's two endpoints: a
    speciesKey-faceted occurrence search (paginated) and per-key species lookups.
    Records every URL requested so tests can assert on pagination termination."""

    def __init__(self):
        self.calls: list[str] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        if url.endswith("/occurrence/search"):
            offset = params["facetOffset"]
            if offset == 0:
                counts = [{"name": "1001", "count": 42}, {"name": "1002", "count": 7}]
            elif offset == 2:
                counts = [{"name": "1003", "count": 3}]
            else:
                counts = []
            facets = [{"field": "SPECIES_KEY", "counts": counts}] if counts else []
            return _FakeResponse({"facets": facets})
        if url.endswith("/species/1001"):
            return _FakeResponse(
                {"canonicalName": "Vanessa atalanta", "rank": "SPECIES", "family": "Nymphalidae", "genus": "Vanessa"}
            )
        if url.endswith("/species/1002"):
            return _FakeResponse({"canonicalName": "Danaus plexippus", "rank": "SPECIES"})
        if url.endswith("/species/1003"):
            # Simulates a speciesKey with no resolvable species record.
            return _FakeResponse({}, status_code=404)
        raise AssertionError(f"Unexpected GBIF URL requested in test: {url}")


class GBIFRegionalSourceParsingTest(TestCase):
    def test_fetch_species_parses_facets_and_resolves_names(self):
        """fetch_species pages the speciesKey facet until a partial page ends it,
        resolves each key to a name (skipping keys GBIF can't resolve), and carries
        the per-species observation count and raw hierarchy fields through."""
        source = GBIFRegionalSource(facet_page_size=2)
        fake_session = _FakeGBIFSession()

        with mock.patch("ami.main.services.gbif.create_session", return_value=fake_session):
            species = source.fetch_species("USA.46_1", LEPIDOPTERA_SCOPE)

        names = {s.scientific_name for s in species}
        self.assertEqual(names, {"Vanessa atalanta", "Danaus plexippus"})

        # Two facet pages (offset 0 full, offset 2 partial) — pagination stopped at
        # the partial page rather than issuing a third, empty-page request.
        occurrence_calls = [c for c in fake_session.calls if c.endswith("/occurrence/search")]
        self.assertEqual(len(occurrence_calls), 2)

        atalanta = next(s for s in species if s.scientific_name == "Vanessa atalanta")
        self.assertEqual(atalanta.gbif_taxon_key, 1001)
        self.assertEqual(atalanta.observation_count, 42)
        self.assertEqual(atalanta.raw["family"], "Nymphalidae")


class MergeSourceSpeciesTest(TestCase):
    def test_union_keeps_species_present_in_only_one_source(self):
        """A species reported by only one source still survives the merge — a
        second source can only grow the candidate set, never narrow it."""
        gbif_only = SourceSpecies(source="gbif_gadm", scientific_name="Danaus plexippus", gbif_taxon_key=1)
        inat_only = SourceSpecies(source="inat_place", scientific_name="Vanessa cardui", inat_taxon_id=2)

        merged = merge_source_species([[gbif_only], [inat_only]])

        self.assertEqual({m.scientific_name for m in merged}, {"Danaus plexippus", "Vanessa cardui"})

    def test_shared_gbif_key_collapses_to_one_row_with_unioned_provenance(self):
        """Two sources reporting the same species (matched by gbif_taxon_key) merge
        into one MergedSpecies carrying both sources and both observation counts."""
        gbif_row = SourceSpecies(
            source="gbif_gadm", scientific_name="Vanessa atalanta", gbif_taxon_key=100, observation_count=50
        )
        inat_row = SourceSpecies(
            source="inat_place", scientific_name="Vanessa atalanta", gbif_taxon_key=100, observation_count=30
        )

        merged = merge_source_species([[gbif_row], [inat_row]])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].sources, {"gbif_gadm", "inat_place"})
        self.assertEqual(merged[0].observation_counts, {"gbif_gadm": 50, "inat_place": 30})

    def test_row_merges_via_whichever_of_its_keys_matches_first(self):
        """Dedup checks a row's gbif key, then its inat key, then its name against
        the index — a row whose gbif key is new but whose inat key matches an
        existing group still collapses into that group instead of starting a new one."""
        first = SourceSpecies(source="gbif_gadm", scientific_name="Vanessa cardui", gbif_taxon_key=1, inat_taxon_id=9)
        second = SourceSpecies(
            source="inat_place", scientific_name="Vanessa cardui", gbif_taxon_key=2, inat_taxon_id=9
        )

        merged = merge_source_species([[first], [second]])

        self.assertEqual(len(merged), 1)
        # The original gbif key is preserved rather than overwritten by the conflicting one.
        self.assertEqual(merged[0].gbif_taxon_key, 1)

    def test_name_only_collision_with_conflicting_keys_keeps_both_and_logs(self):
        """Two rows sharing only a normalized name but carrying different GBIF keys
        merge into one row (name-only collision) rather than becoming two rows, and
        the conflict is logged instead of silently dropping a key."""
        first = SourceSpecies(source="gbif_gadm", scientific_name="Vanessa cardui", gbif_taxon_key=1)
        second = SourceSpecies(source="inat_place", scientific_name="Vanessa cardui", gbif_taxon_key=2)

        with self.assertLogs("ami.main.services.regional_taxa", level="WARNING"):
            merged = merge_source_species([[first], [second]])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].sources, {"gbif_gadm", "inat_place"})


class MapToTaxaTest(TestCase):
    def test_matches_existing_taxon_by_gbif_key(self):
        existing = Taxon.objects.create(name="Papilio machaon", rank=TaxonRank.SPECIES.name, gbif_taxon_key=100)
        species = MergedSpecies(
            scientific_name="Papilio machaon",
            rank="SPECIES",
            gbif_taxon_key=100,
            inat_taxon_id=None,
            sources={"gbif_gadm"},
            observation_counts={},
            contributing=[],
        )

        outcome = map_to_taxa([species], create_missing=True, dry_run=False)

        self.assertEqual(outcome.matched, [(species, existing)])
        self.assertEqual(outcome.created, [])

    def test_matches_existing_taxon_by_name(self):
        existing = Taxon.objects.create(name="Danaus plexippus", rank=TaxonRank.SPECIES.name)
        species = MergedSpecies(
            scientific_name="Danaus plexippus",
            rank="SPECIES",
            gbif_taxon_key=None,
            inat_taxon_id=None,
            sources={"gbif_gadm"},
            observation_counts={},
            contributing=[],
        )

        outcome = map_to_taxa([species], create_missing=True, dry_run=False)

        self.assertEqual(outcome.matched, [(species, existing)])

    def test_create_missing_creates_taxon_via_hierarchy_builder(self):
        """When no existing Taxon matches, create_missing builds one (and its
        ancestors) via the same rank-hierarchy builder import_taxa uses, from
        whatever hierarchy fields a contributing source's raw payload carries."""
        contributing = SourceSpecies(
            source="gbif_gadm",
            scientific_name="Papilio glaucus",
            gbif_taxon_key=555,
            raw={"family": "Papilionidae", "genus": "Papilio"},
        )
        species = MergedSpecies(
            scientific_name="Papilio glaucus",
            rank="SPECIES",
            gbif_taxon_key=555,
            inat_taxon_id=None,
            sources={"gbif_gadm"},
            observation_counts={},
            contributing=[contributing],
        )

        outcome = map_to_taxa([species], create_missing=True, dry_run=False)

        self.assertEqual(len(outcome.created), 1)
        taxon = outcome.created[0]
        self.assertEqual(taxon.name, "Papilio glaucus")
        self.assertEqual(taxon.gbif_taxon_key, 555)
        self.assertEqual(taxon.parent.name, "Papilio")
        self.assertEqual(taxon.parent.parent.name, "Papilionidae")

    def test_create_missing_false_records_unmatched_name_without_creating(self):
        species = MergedSpecies(
            scientific_name="Unknown species",
            rank="SPECIES",
            gbif_taxon_key=None,
            inat_taxon_id=None,
            sources={"gbif_gadm"},
            observation_counts={},
            contributing=[],
        )

        outcome = map_to_taxa([species], create_missing=False, dry_run=False)

        self.assertEqual(outcome.unmatched_names, ["Unknown species"])
        self.assertEqual(outcome.created, [])
        self.assertFalse(Taxon.objects.filter(name="Unknown species").exists())

    def test_rerun_does_not_create_duplicate_taxon(self):
        """Running map_to_taxa twice for the same species must not create a second
        Taxon row — the second call matches the row the first call created, via the
        existing-Taxon name lookup (Taxon.name is unique)."""
        species = MergedSpecies(
            scientific_name="Papilio glaucus",
            rank="SPECIES",
            gbif_taxon_key=None,
            inat_taxon_id=None,
            sources={"gbif_gadm"},
            observation_counts={},
            contributing=[],
        )

        map_to_taxa([species], create_missing=True, dry_run=False)
        map_to_taxa([species], create_missing=True, dry_run=False)

        self.assertEqual(Taxon.objects.filter(name="Papilio glaucus").count(), 1)

    def test_dry_run_never_creates_a_taxon_row(self):
        """dry_run must not mutate the DB — a species that would be created is
        represented as an unsaved Taxon stand-in instead."""
        species = MergedSpecies(
            scientific_name="Ghost Species",
            rank="SPECIES",
            gbif_taxon_key=None,
            inat_taxon_id=None,
            sources={"gbif_gadm"},
            observation_counts={},
            contributing=[],
        )

        outcome = map_to_taxa([species], create_missing=True, dry_run=True)

        self.assertEqual(len(outcome.created), 1)
        self.assertIsNone(outcome.created[0].pk)
        self.assertFalse(Taxon.objects.filter(name="Ghost Species").exists())

    def test_matching_existing_taxa_is_batched_not_per_row(self):
        """The existing-Taxon lookup is three bulk `__in` queries regardless of how
        many merged species are being matched — never one query per species."""
        taxa = [
            Taxon.objects.create(name=f"Species {i}", rank=TaxonRank.SPECIES.name, gbif_taxon_key=1000 + i)
            for i in range(5)
        ]
        merged = [
            MergedSpecies(
                scientific_name=taxon.name,
                rank="SPECIES",
                gbif_taxon_key=taxon.gbif_taxon_key,
                inat_taxon_id=None,
                sources={"gbif_gadm"},
                observation_counts={},
                contributing=[],
            )
            for taxon in taxa
        ]

        # gbif_taxon_key __in lookup + name __in lookup; no inat ids given, so that
        # lookup is skipped. Neither query scales with len(merged).
        with self.assertNumQueries(2):
            outcome = map_to_taxa(merged, create_missing=False, dry_run=False)

        self.assertEqual(len(outcome.matched), 5)


class GenerateRegionalTaxaListTest(TestCase):
    class StubSource:
        def __init__(self, source_key: str, species: list[SourceSpecies]):
            self.source_key = source_key
            self._species = species

        def fetch_species(self, region_code, taxon_scope):
            return list(self._species)

    def test_rerun_updates_same_taxa_list_not_a_duplicate(self):
        project = Project.objects.create(name="Regional Test Project", create_defaults=False)
        source = self.StubSource(
            "gbif_gadm", [SourceSpecies(source="gbif_gadm", scientific_name="Colias eurytheme", gbif_taxon_key=1)]
        )

        result1 = generate_regional_taxa_list(
            region_source=RegionSource.GBIF_GADM,
            region_code="USA.46_1",
            project=project,
            sources=[source],
            name="Vermont Moths",
            include_uncovered=True,
        )
        result2 = generate_regional_taxa_list(
            region_source=RegionSource.GBIF_GADM,
            region_code="USA.46_1",
            project=project,
            sources=[source],
            name="Vermont Moths",
            include_uncovered=True,
        )

        self.assertTrue(result1.list_created)
        self.assertFalse(result2.list_created)
        self.assertEqual(result1.taxa_list_id, result2.taxa_list_id)
        self.assertEqual(TaxaList.objects.filter(name="Vermont Moths", projects=project).count(), 1)
        self.assertEqual(Taxon.objects.filter(name="Colias eurytheme").count(), 1)
        taxa_list = TaxaList.objects.get(pk=result2.taxa_list_id)
        self.assertEqual(list(taxa_list.taxa.values_list("name", flat=True)), ["Colias eurytheme"])

    def test_classifier_report_is_report_only_does_not_filter_list(self):
        """Passing classifier= only populates in_classifier_labels/not_in_classifier;
        the saved list is governed solely by the ordinary model-coverage rule."""
        project = Project.objects.create(name="Regional Test Project", create_defaults=False)
        covered_taxon = Taxon.objects.create(name="Covered Species", rank=TaxonRank.SPECIES.name)
        coverage_map = AlgorithmCategoryMap.objects.create(
            labels=["Covered Species"], data=[{"index": 0, "label": "Covered Species"}]
        )
        Algorithm.objects.create(name="Coverage Classifier", version=1, category_map=coverage_map)
        covered_taxon.refresh_from_db()
        self.assertTrue(covered_taxon.has_model_coverage)

        # A different classifier whose own labels do NOT include "Covered Species" —
        # exercises that the report is scoped to the one classifier passed in, not
        # to whichever classifier happened to give the taxon model coverage.
        reporting_map = AlgorithmCategoryMap.objects.create(
            labels=["Some Other Label"], data=[{"index": 0, "label": "Some Other Label"}]
        )
        reporting_classifier = Algorithm.objects.create(
            name="Reporting Classifier", version=1, category_map=reporting_map
        )

        source = self.StubSource(
            "gbif_gadm", [SourceSpecies(source="gbif_gadm", scientific_name="Covered Species", gbif_taxon_key=1)]
        )

        result = generate_regional_taxa_list(
            region_source=RegionSource.GBIF_GADM,
            region_code="USA.46_1",
            project=project,
            sources=[source],
            classifier=reporting_classifier,
        )

        self.assertEqual(result.saved_list_size, 1)
        self.assertEqual(result.in_classifier_labels, 0)
        self.assertEqual(result.not_in_classifier, 1)

    def test_default_saves_only_model_covered_species(self):
        """A region with a mix of covered and uncovered species: the default run
        saves only the covered ones. The uncovered species' Taxon row still gets
        created (create_missing's default), it's just excluded from this list."""
        project = Project.objects.create(name="Regional Test Project", create_defaults=False)
        covered_taxon = Taxon.objects.create(name="Covered Species", rank=TaxonRank.SPECIES.name)
        coverage_map = AlgorithmCategoryMap.objects.create(
            labels=["Covered Species"], data=[{"index": 0, "label": "Covered Species"}]
        )
        Algorithm.objects.create(name="Coverage Classifier", version=1, category_map=coverage_map)
        covered_taxon.refresh_from_db()
        self.assertTrue(covered_taxon.has_model_coverage)

        source = self.StubSource(
            "gbif_gadm",
            [
                SourceSpecies(source="gbif_gadm", scientific_name="Covered Species", gbif_taxon_key=1),
                SourceSpecies(source="gbif_gadm", scientific_name="Uncovered Species", gbif_taxon_key=2),
            ],
        )

        result = generate_regional_taxa_list(
            region_source=RegionSource.GBIF_GADM, region_code="USA.46_1", project=project, sources=[source]
        )

        self.assertEqual(result.regional_total, 2)
        self.assertEqual(result.model_covered, 1)
        self.assertEqual(result.regional_no_model_coverage, 1)
        self.assertEqual(result.saved_list_size, 1)
        taxa_list = TaxaList.objects.get(pk=result.taxa_list_id)
        self.assertEqual(set(taxa_list.taxa.values_list("name", flat=True)), {"Covered Species"})
        self.assertTrue(Taxon.objects.filter(name="Uncovered Species").exists())

    def test_include_uncovered_creates_and_flags_uncovered_species(self):
        """Opting in keeps both buckets: covered species stay flagged True, and the
        newly created uncovered species are flagged has_model_coverage=False with an
        empty covered_by_algorithms — an honest "in the region, no model knows it yet"."""
        project = Project.objects.create(name="Regional Test Project", create_defaults=False)
        covered_taxon = Taxon.objects.create(name="Covered Species", rank=TaxonRank.SPECIES.name)
        coverage_map = AlgorithmCategoryMap.objects.create(
            labels=["Covered Species"], data=[{"index": 0, "label": "Covered Species"}]
        )
        Algorithm.objects.create(name="Coverage Classifier", version=1, category_map=coverage_map)
        covered_taxon.refresh_from_db()

        source = self.StubSource(
            "gbif_gadm",
            [
                SourceSpecies(source="gbif_gadm", scientific_name="Covered Species", gbif_taxon_key=1),
                SourceSpecies(source="gbif_gadm", scientific_name="Uncovered Species", gbif_taxon_key=2),
            ],
        )

        result = generate_regional_taxa_list(
            region_source=RegionSource.GBIF_GADM,
            region_code="USA.46_1",
            project=project,
            sources=[source],
            include_uncovered=True,
        )

        self.assertEqual(result.saved_list_size, 2)
        taxa_list = TaxaList.objects.get(pk=result.taxa_list_id)
        self.assertEqual(set(taxa_list.taxa.values_list("name", flat=True)), {"Covered Species", "Uncovered Species"})

        uncovered = Taxon.objects.get(name="Uncovered Species")
        self.assertFalse(uncovered.has_model_coverage)
        self.assertEqual(uncovered.covered_by_algorithms.count(), 0)

        covered_taxon.refresh_from_db()
        self.assertTrue(covered_taxon.has_model_coverage)

    def test_dry_run_never_mutates_the_database(self):
        project = Project.objects.create(name="Regional Test Project", create_defaults=False)
        source = self.StubSource(
            "gbif_gadm", [SourceSpecies(source="gbif_gadm", scientific_name="Ghost Species", gbif_taxon_key=1)]
        )

        result = generate_regional_taxa_list(
            region_source=RegionSource.GBIF_GADM,
            region_code="USA.46_1",
            project=project,
            sources=[source],
            include_uncovered=True,
            dry_run=True,
        )

        self.assertTrue(result.dry_run)
        self.assertIsNone(result.taxa_list_id)
        self.assertEqual(result.created_taxa, 1)
        self.assertFalse(Taxon.objects.filter(name="Ghost Species").exists())
        self.assertFalse(TaxaList.objects.filter(projects=project).exists())


class TaxonModelCoverageRefreshTest(TestCase):
    def test_linking_a_category_map_hook_sets_coverage(self):
        """Linking an algorithm to a category map that lists a taxon's name as a
        label marks that taxon has_model_coverage=True and adds the algorithm to
        its covered_by_algorithms, via the Algorithm.save() hook — no explicit
        refresh call needed."""
        taxon = Taxon.objects.create(name="Covered Species", rank=TaxonRank.SPECIES.name)
        category_map = AlgorithmCategoryMap.objects.create(
            labels=["Covered Species"], data=[{"index": 0, "label": "Covered Species"}]
        )

        algorithm = Algorithm.objects.create(name="Test Classifier", version=1, category_map=category_map)

        taxon.refresh_from_db()
        self.assertTrue(taxon.has_model_coverage)
        self.assertIn(algorithm, taxon.covered_by_algorithms.all())
        self.assertIn(taxon, algorithm.covered_taxa.all())

    def test_reassigning_the_category_map_drops_stale_coverage(self):
        """When an algorithm's category map is swapped for one that no longer lists
        a taxon, the hook-triggered refresh removes that taxon's coverage (assuming
        no other algorithm still covers it)."""
        taxon = Taxon.objects.create(name="Covered Species", rank=TaxonRank.SPECIES.name)
        map_v1 = AlgorithmCategoryMap.objects.create(
            labels=["Covered Species"], data=[{"index": 0, "label": "Covered Species"}]
        )
        algorithm = Algorithm.objects.create(name="Test Classifier", version=1, category_map=map_v1)
        taxon.refresh_from_db()
        self.assertTrue(taxon.has_model_coverage)

        map_v2 = AlgorithmCategoryMap.objects.create(
            labels=["Some Other Species"], data=[{"index": 0, "label": "Some Other Species"}]
        )
        algorithm.category_map = map_v2
        algorithm.save()

        taxon.refresh_from_db()
        self.assertFalse(taxon.has_model_coverage)
        self.assertEqual(taxon.covered_by_algorithms.count(), 0)

    def test_refresh_command_repairs_coverage_the_hook_never_saw(self):
        """The full-rebuild management command recomputes coverage for every
        algorithm's category map, correcting drift from a write path that bypasses
        the per-save hook (e.g. a bulk_update on Algorithm.category_map)."""
        taxon = Taxon.objects.create(name="Covered Species", rank=TaxonRank.SPECIES.name)
        category_map = AlgorithmCategoryMap.objects.create(
            labels=["Covered Species"], data=[{"index": 0, "label": "Covered Species"}]
        )
        algorithm = Algorithm.objects.create(name="Test Classifier", version=1)
        # bulk_update never calls Algorithm.save(), so the hook never fires.
        Algorithm.objects.filter(pk=algorithm.pk).update(category_map=category_map)
        taxon.refresh_from_db()
        self.assertFalse(taxon.has_model_coverage)

        call_command("refresh_taxon_model_coverage")

        taxon.refresh_from_db()
        self.assertTrue(taxon.has_model_coverage)
        algorithm.refresh_from_db()
        self.assertIn(taxon, algorithm.covered_taxa.all())

    def test_covering_algorithms_are_reachable_from_the_taxon(self):
        """taxon.covered_by_algorithms.all() names the algorithm(s) that cover a
        taxon, so callers can show which model knows a species, not just whether
        one does."""
        taxon = Taxon.objects.create(name="Covered Species", rank=TaxonRank.SPECIES.name)
        category_map = AlgorithmCategoryMap.objects.create(
            labels=["Covered Species"], data=[{"index": 0, "label": "Covered Species"}]
        )

        algorithm = Algorithm.objects.create(name="Test Classifier", version=1, category_map=category_map)

        self.assertEqual(list(taxon.covered_by_algorithms.all()), [algorithm])


class ApplyModelCoverageDryRunTest(TestCase):
    def test_dry_run_partition_is_read_only(self):
        """apply_model_coverage's dry_run path checks unsaved stand-in taxa against
        current category map labels without writing anything, and still correctly
        partitions covered vs. uncovered."""
        AlgorithmCategoryMap.objects.create(
            labels=["Covered Species"], data=[{"index": 0, "label": "Covered Species"}]
        )
        merged = [
            MergedSpecies(
                scientific_name="Covered Species",
                rank="SPECIES",
                gbif_taxon_key=None,
                inat_taxon_id=None,
                sources={"gbif_gadm"},
                observation_counts={},
                contributing=[],
            ),
            MergedSpecies(
                scientific_name="Uncovered Species",
                rank="SPECIES",
                gbif_taxon_key=None,
                inat_taxon_id=None,
                sources={"gbif_gadm"},
                observation_counts={},
                contributing=[],
            ),
        ]

        mapping = map_to_taxa(merged, create_missing=True, dry_run=True)
        coverage = apply_model_coverage(mapping, dry_run=True)

        self.assertEqual({t.name for t in coverage.covered}, {"Covered Species"})
        self.assertEqual({t.name for t in coverage.uncovered}, {"Uncovered Species"})
        # dry_run must not persist either stand-in Taxon.
        self.assertFalse(Taxon.objects.filter(name__in=["Covered Species", "Uncovered Species"]).exists())
