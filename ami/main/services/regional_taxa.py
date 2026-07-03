"""Build a project taxa list from a geographic region.

Fetches the species recorded in a region from one or more external biodiversity
databases (currently GBIF; iNaturalist can be added behind the same protocol), maps
them onto Antenna `Taxon` rows, restricts the result (by default) to species some
classifier can actually predict, and saves a project-scoped `TaxaList`. This is the
one place the logic lives; management commands, admin actions, and API endpoints are
thin wrappers around `generate_regional_taxa_list()`. See issue #1364 and the
accompanying design/implementation-plan docs for the full rationale.

The one design rule everything here is built around: when more than one source is
queried, a species present in ANY source is a candidate for the regional list.
Sources are combined with a wide union, never an intersection — querying a second
source can only grow the candidate set. Model coverage (does some classifier know
this species) is a separate, later axis applied after mapping to `Taxon`, not part of
how sources combine.
"""

from __future__ import annotations

import dataclasses
import logging
import typing

from ..models import RegionSource, Taxon, TaxonRank
from . import taxon_coverage
from .taxonomy import create_taxon, get_or_create_root_taxon

if typing.TYPE_CHECKING:
    from ami.ml.models.algorithm import Algorithm

    from ..models import Project

logger = logging.getLogger(__name__)


# --- Source abstraction -------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SourceSpecies:
    """One species as reported by ONE source for a region.

    The merge step (`merge_source_species`) concatenates these across sources and
    deduplicates on a canonical key, unioning provenance. Fields are deliberately
    source-agnostic so a new source only has to populate what it knows; `raw` carries
    the untouched source payload for fields not yet promoted to the dataclass (e.g.
    the genus/family hierarchy GBIF's species endpoint returns, used to build a
    richer `Taxon` parent chain when creating a missing taxon).
    """

    source: str
    scientific_name: str
    rank: str | None = None
    gbif_taxon_key: int | None = None
    inat_taxon_id: int | None = None
    observation_count: int | None = None
    raw: dict | None = None


@dataclasses.dataclass
class MergedSpecies:
    """One species after the wide union merge, with per-source provenance preserved."""

    scientific_name: str
    rank: str | None
    gbif_taxon_key: int | None
    inat_taxon_id: int | None
    sources: set[str]
    observation_counts: dict[str, int]
    contributing: list[SourceSpecies]


@dataclasses.dataclass(frozen=True)
class TaxonScope:
    """Source-specific root-taxon identifiers for a scope like "Lepidoptera", so a
    caller names the scope once and each source translates it to its own key."""

    label: str
    gbif_taxon_key: int | None = None
    inat_taxon_id: int | None = None


# GBIF backbone taxonKey 797 / iNaturalist taxon_id 47157 for Lepidoptera, verified
# live against both APIs in the #1364 Phase 0 spike (see docs/claude/analysis).
LEPIDOPTERA_SCOPE = TaxonScope(label="Lepidoptera", gbif_taxon_key=797, inat_taxon_id=47157)


class RegionalSpeciesSource(typing.Protocol):
    source_key: str

    def fetch_species(self, region_code: str, taxon_scope: TaxonScope) -> list[SourceSpecies]:
        """Return every species the source records in `region_code`, within
        `taxon_scope`. Paginates internally; raises on transport/HTTP error rather
        than returning a partial list silently."""
        ...


# --- Wide merge -----------------------------------------------------------------


def _normalize_name(name: str) -> str:
    return " ".join(name.casefold().split())


def _dedup_keys(row: SourceSpecies) -> list[tuple[str, object]]:
    """Every key `row` could be matched on, in dedup precedence order: gbif, inat,
    name. A row usually supplies a subset of these."""
    keys: list[tuple[str, object]] = []
    if row.gbif_taxon_key:
        keys.append(("gbif", row.gbif_taxon_key))
    if row.inat_taxon_id:
        keys.append(("inat", row.inat_taxon_id))
    if row.scientific_name:
        keys.append(("name", _normalize_name(row.scientific_name)))
    return keys


def merge_source_species(per_source: list[list[SourceSpecies]]) -> list[MergedSpecies]:
    """Concatenate species across sources and deduplicate on a canonical key,
    UNIONING provenance. This is a wide join, never an intersection: a species in ANY
    source survives. Two source rows collapse into one MergedSpecies when they share
    a canonical key (gbif_taxon_key, then inat_taxon_id, then normalized name — first
    match wins). A name-only collision with conflicting external keys keeps both keys
    (logged as a provenance warning) rather than silently dropping one.

    Output is stable-ordered by descending max observation count, then name, so runs
    are reproducible and diffs are readable.
    """
    key_index: dict[tuple[str, object], MergedSpecies] = {}
    order: list[MergedSpecies] = []

    for species_list in per_source:
        for row in species_list:
            keys = _dedup_keys(row)
            if not keys:
                continue

            existing = next((key_index[k] for k in keys if k in key_index), None)
            if existing is None:
                merged = MergedSpecies(
                    scientific_name=row.scientific_name,
                    rank=row.rank,
                    gbif_taxon_key=row.gbif_taxon_key,
                    inat_taxon_id=row.inat_taxon_id,
                    sources={row.source},
                    observation_counts=(
                        {row.source: row.observation_count} if row.observation_count is not None else {}
                    ),
                    contributing=[row],
                )
                order.append(merged)
                for k in keys:
                    key_index[k] = merged
                continue

            existing.sources.add(row.source)
            if row.observation_count is not None:
                existing.observation_counts[row.source] = row.observation_count
            existing.contributing.append(row)

            if row.gbif_taxon_key and existing.gbif_taxon_key and row.gbif_taxon_key != existing.gbif_taxon_key:
                logger.warning(
                    "Regional species merge: %r has conflicting GBIF keys (%s vs %s); keeping both as provenance",
                    row.scientific_name,
                    existing.gbif_taxon_key,
                    row.gbif_taxon_key,
                )
            elif row.gbif_taxon_key and not existing.gbif_taxon_key:
                existing.gbif_taxon_key = row.gbif_taxon_key
                key_index[("gbif", row.gbif_taxon_key)] = existing

            if row.inat_taxon_id and existing.inat_taxon_id and row.inat_taxon_id != existing.inat_taxon_id:
                logger.warning(
                    "Regional species merge: %r has conflicting iNat ids (%s vs %s); keeping both as provenance",
                    row.scientific_name,
                    existing.inat_taxon_id,
                    row.inat_taxon_id,
                )
            elif row.inat_taxon_id and not existing.inat_taxon_id:
                existing.inat_taxon_id = row.inat_taxon_id
                key_index[("inat", row.inat_taxon_id)] = existing

            for k in keys:
                key_index.setdefault(k, existing)

    order.sort(key=lambda m: (-(max(m.observation_counts.values()) if m.observation_counts else 0), m.scientific_name))
    return order


# --- Mapping to Taxon -------------------------------------------------------------


@dataclasses.dataclass
class MappingOutcome:
    matched: list[tuple[MergedSpecies, Taxon]]
    created: list[Taxon]
    unmatched_names: list[str]


_HIERARCHY_FIELDS = ("kingdom", "phylum", "class", "order", "family", "subfamily", "tribe", "genus")


def _taxon_data_from_merged(species: MergedSpecies) -> dict:
    """Build the row-shaped dict `create_taxon()` expects (see
    ami.main.services.taxonomy), from whatever hierarchy fields a contributing
    source's raw payload carries (e.g. GBIF's genus/family/order), falling back to
    just the species-level name when a source gives no hierarchy — still a valid,
    if flat, Taxon parented directly under the root.
    """
    taxon_data: dict = {}
    for row in species.contributing:
        if not row.raw:
            continue
        for field in _HIERARCHY_FIELDS:
            value = row.raw.get(field)
            if value and field not in taxon_data:
                taxon_data[field] = value

    rank_key = (species.rank or TaxonRank.SPECIES.name).lower()
    taxon_data[rank_key] = species.scientific_name
    if species.gbif_taxon_key:
        taxon_data["gbif_taxon_key"] = species.gbif_taxon_key
    if species.inat_taxon_id:
        taxon_data["inat_taxon_id"] = species.inat_taxon_id
    return taxon_data


def map_to_taxa(merged: list[MergedSpecies], *, create_missing: bool, dry_run: bool) -> MappingOutcome:
    """Resolve each MergedSpecies to a Taxon. Match precedence: gbif_taxon_key, then
    inat_taxon_id, then exact Taxon.name. On no match: create via the rank-hierarchy
    builder when create_missing, else record the name as unmatched for human review.
    Never mutates on dry_run — unmatched species that would be created are
    represented as unsaved Taxon instances instead, so Result counts still reflect
    what a real run would do.
    """
    gbif_keys = {m.gbif_taxon_key for m in merged if m.gbif_taxon_key}
    inat_ids = {m.inat_taxon_id for m in merged if m.inat_taxon_id}
    names = {m.scientific_name for m in merged}

    by_gbif_key = (
        {t.gbif_taxon_key: t for t in Taxon.objects.filter(gbif_taxon_key__in=gbif_keys)} if gbif_keys else {}
    )
    by_inat_id = {t.inat_taxon_id: t for t in Taxon.objects.filter(inat_taxon_id__in=inat_ids)} if inat_ids else {}
    by_name = {t.name: t for t in Taxon.objects.filter(name__in=names)} if names else {}

    matched: list[tuple[MergedSpecies, Taxon]] = []
    created: list[Taxon] = []
    unmatched_names: list[str] = []
    root_taxon: Taxon | None = None

    for species in merged:
        taxon = None
        if species.gbif_taxon_key and species.gbif_taxon_key in by_gbif_key:
            taxon = by_gbif_key[species.gbif_taxon_key]
        elif species.inat_taxon_id and species.inat_taxon_id in by_inat_id:
            taxon = by_inat_id[species.inat_taxon_id]
        elif species.scientific_name in by_name:
            taxon = by_name[species.scientific_name]

        if taxon is not None:
            matched.append((species, taxon))
            continue

        if not create_missing:
            unmatched_names.append(species.scientific_name)
            continue

        if dry_run:
            created.append(
                Taxon(
                    name=species.scientific_name,
                    rank=(species.rank or TaxonRank.SPECIES.name).upper(),
                    gbif_taxon_key=species.gbif_taxon_key,
                    inat_taxon_id=species.inat_taxon_id,
                )
            )
            continue

        if root_taxon is None:
            root_taxon = get_or_create_root_taxon()
        _created_taxa, _updated_taxa, specific_taxon = create_taxon(_taxon_data_from_merged(species), root_taxon)
        created.append(specific_taxon)

    return MappingOutcome(matched=matched, created=created, unmatched_names=unmatched_names)


# --- Model coverage ----------------------------------------------------------------


@dataclasses.dataclass
class CoverageOutcome:
    covered: list[Taxon]
    uncovered: list[Taxon]


def apply_model_coverage(mapping: MappingOutcome, *, dry_run: bool) -> CoverageOutcome:
    """Partition mapped taxa into model-covered vs. uncovered using the persisted
    has_model_coverage relationship (ami.main.services.taxon_coverage) — not a live
    recompute for taxa that already existed before this run, whose coverage flag is
    kept fresh by the Algorithm.save() hook / refresh_taxon_model_coverage command.

    Newly created taxa are the one exception: they have no coverage relationship yet
    (they didn't exist for the hook to act on), so a real (non-dry_run) run refreshes
    coverage before partitioning them. dry_run never writes, so newly-would-be-created
    taxa are checked read-only against current category map labels instead.
    """
    matched_taxa = [taxon for _, taxon in mapping.matched]
    created_taxa = mapping.created

    if dry_run:
        would_cover = taxon_coverage.names_covered_by_any_algorithm({t.name for t in created_taxa})
        covered = [t for t in matched_taxa if t.has_model_coverage]
        covered += [t for t in created_taxa if t.name in would_cover]
        uncovered = [t for t in matched_taxa if not t.has_model_coverage]
        uncovered += [t for t in created_taxa if t.name not in would_cover]
        return CoverageOutcome(covered=covered, uncovered=uncovered)

    if created_taxa:
        # Give just-created taxa a coverage state before partitioning them. A targeted
        # refresh (only these taxa) keeps the --all-projects backfill from paying a
        # full per-algorithm rebuild on every project that creates a taxon.
        taxon_coverage.refresh_coverage_for_taxa([t.pk for t in created_taxa])
        fresh_by_id = {t.pk: t for t in Taxon.objects.filter(pk__in=[t.pk for t in created_taxa])}
        created_taxa = [fresh_by_id[t.pk] for t in created_taxa if t.pk in fresh_by_id]

    all_taxa = matched_taxa + created_taxa
    covered = [t for t in all_taxa if t.has_model_coverage]
    uncovered = [t for t in all_taxa if not t.has_model_coverage]
    return CoverageOutcome(covered=covered, uncovered=uncovered)


# --- Core service --------------------------------------------------------------------


@dataclasses.dataclass
class RegionalTaxaResult:
    region_source: str
    region_code: str
    taxa_list_id: int | None
    list_created: bool
    # --- source union ---
    regional_total: int
    per_source_counts: dict[str, int]
    # --- DB presence & model coverage ---
    already_in_db: int
    created_taxa: int
    model_covered: int
    regional_no_model_coverage: int
    saved_list_size: int
    # --- optional single-classifier report (reporting only; never filters the list) ---
    in_classifier_labels: int | None
    not_in_classifier: int | None
    # --- review ---
    unmatched_names: list[str]
    dry_run: bool


def _default_sources(region_source: str) -> list[RegionalSpeciesSource]:
    if region_source == RegionSource.GBIF_GADM:
        from .gbif import GBIFRegionalSource

        return [GBIFRegionalSource()]
    raise ValueError(
        f"No default regional species source is registered for region_source={region_source!r}. "
        "Pass sources= explicitly, or use RegionSource.GBIF_GADM (the only source implemented so far)."
    )


def generate_regional_taxa_list(
    *,
    region_source: str,
    region_code: str,
    project: Project | None = None,
    classifier: Algorithm | None = None,
    taxon_scope: TaxonScope | None = None,
    sources: list[RegionalSpeciesSource] | None = None,
    include_uncovered: bool = False,
    create_missing: bool = True,
    name: str | None = None,
    dry_run: bool = False,
) -> RegionalTaxaResult:
    """Fetch the species recorded in a region, map them to Taxon rows, and save them
    as a project-scoped TaxaList.

    `sources` is the dependency-injection seam: pass stubbed sources in tests so
    nothing hits the network. When omitted, the default source client for
    `region_source` is used (currently GBIF only).

    Idempotent: a second run for the same (name, project) updates the same TaxaList
    rather than creating a duplicate — re-running never creates duplicate lists or
    duplicate Taxon rows (name-unique + external-key matching handle that).
    """
    from ..models import TaxaList

    taxon_scope = taxon_scope or LEPIDOPTERA_SCOPE
    resolved_sources = sources if sources is not None else _default_sources(region_source)

    per_source_species = [source.fetch_species(region_code, taxon_scope) for source in resolved_sources]
    per_source_counts = {
        source.source_key: len(species) for source, species in zip(resolved_sources, per_source_species)
    }

    merged = merge_source_species(per_source_species)
    regional_total = len(merged)

    mapping = map_to_taxa(merged, create_missing=create_missing, dry_run=dry_run)
    coverage = apply_model_coverage(mapping, dry_run=dry_run)

    kept_taxa = list(coverage.covered)
    if include_uncovered:
        kept_taxa += coverage.uncovered

    in_classifier_labels: int | None = None
    not_in_classifier: int | None = None
    if classifier is not None and classifier.category_map is not None:
        classifier_labels = set(classifier.category_map.labels)
        in_classifier_labels = sum(1 for taxon in kept_taxa if taxon.name in classifier_labels)
        not_in_classifier = len(kept_taxa) - in_classifier_labels

    list_name = name or f"{region_code} ({region_source})"
    taxa_list_id: int | None = None
    list_created = False

    if not dry_run:
        taxa_list, list_created = TaxaList.objects.get_or_create_for_project(name=list_name, project=project)
        taxa_list.taxa.set(kept_taxa)
        taxa_list_id = taxa_list.pk

    return RegionalTaxaResult(
        region_source=region_source,
        region_code=region_code,
        taxa_list_id=taxa_list_id,
        list_created=list_created,
        regional_total=regional_total,
        per_source_counts=per_source_counts,
        already_in_db=len(mapping.matched),
        created_taxa=len(mapping.created),
        model_covered=len(coverage.covered),
        regional_no_model_coverage=len(coverage.uncovered),
        saved_list_size=len(kept_taxa),
        in_classifier_labels=in_classifier_labels,
        not_in_classifier=not_in_classifier,
        unmatched_names=mapping.unmatched_names,
        dry_run=dry_run,
    )


def derive_region_for_project(
    project: Project,
    *,
    region_source: str = RegionSource.GBIF_GADM.value,
    level: int = 1,
    geocoder: typing.Callable[..., str | None] | None = None,
) -> tuple[str, str] | None:
    """Derive a (region_source, region_code) for a project from a representative
    deployment's coordinates (issue #1364, path A3).

    This is what lets the `--all-projects` backfill run without anyone entering a
    region by hand: it reverse-geocodes the first deployment that has coordinates.
    Returns None when the project has no located deployment or the point falls
    outside any GADM region of `level`, so the caller can skip that project. GBIF/GADM
    is the only supported source for now. `geocoder` is a test seam — inject a stub to
    avoid a network call.
    """
    if region_source != RegionSource.GBIF_GADM:
        raise ValueError(f"derive_region_for_project supports GBIF/GADM only, got {region_source!r}")

    deployment = project.deployments.filter(latitude__isnull=False, longitude__isnull=False).order_by("pk").first()
    if deployment is None:
        return None

    if geocoder is None:
        from .gbif import reverse_geocode_gadm

        geocoder = reverse_geocode_gadm

    region_code = geocoder(deployment.latitude, deployment.longitude, level=level)
    if not region_code:
        return None
    return (region_source, region_code)
