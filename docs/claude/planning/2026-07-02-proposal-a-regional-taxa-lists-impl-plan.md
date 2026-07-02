# Implementation plan — Proposal A: build a project taxa list from a region

**Status:** planning (not started)
**Issue:** [#1364](https://github.com/RolnickLab/antenna/issues/1364) — "Let users build a project taxa list from a region, so class masking works out of the box"
**Design doc (authoritative):** `docs/claude/planning/2026-07-02-regional-taxa-lists-class-masking.md`
**Depends on / relates to:** #999 (class masking), #1289 (post-processing framework, merged), #1094 (configurable taxa lists), #939 (import taxa), #1020 (closed — browser GBIF taxon-select, UI reference), #1293 (taxa list CSV export)
**Author:** Claude (agent), 2026-07-02

This document turns the design doc's "Proposal A", "reusable core", "data model", and "resolution order" sections into a staged, test-first implementation plan with concrete file paths, function signatures, and anchors into existing code to reuse. It is a public-repo planning doc: full prose, and every claim about an external API is labelled as unverified until it has been exercised from this codebase.

---

## 1. What we are building and why

Class masking (#999) keeps only the classifier predictions whose taxon appears in a chosen taxa list, cutting a global classifier down to the species that actually occur at a site. The blocker is that the taxa list has to be hand-curated one taxon at a time, and nothing ties a list to the place a project monitors.

Proposal A adds one capability — **"given a region, produce a taxa list"** — written once as a service function and surfaced five ways (management command, unit test, Django admin action, DRF endpoint, main UI). It fetches the species recorded in a geographic region from one or more external biodiversity databases (GBIF, iNaturalist), maps them onto Antenna `Taxon` rows, optionally reports how many fall inside a classifier's label set, and saves a project-scoped `TaxaList`. It also adds region/list fields to `Site` and `Project` and a resolution order so the class-masking task can pick the right list automatically per occurrence.

### 1.1 The one design decision to get right: multiple sources UNION, they do not INTERSECT

When more than one source is queried (GBIF **and** iNaturalist, say), a species present in **any** source is a candidate for the regional list. The sources are combined with a **wide join / concatenation**, not an intersection:

- The merged intermediate is a **wide table**: one row per canonical species, carrying per-source provenance columns — which source(s) contributed the species, each source's native key (`gbif_taxon_key`, `inat_taxon_id`, …), and each source's observation count.
- Sources are **never intersected against each other**. Querying two sources can only grow the candidate set, never shrink it.
- The **only** intersection in the whole flow is the *optional, final, reporting-only* step against a classifier's label set. That intersection does not remove species from the saved list — it only reports "of the N species in this regional list, M are actually in classifier X's labels, so masking will affect M of them." It is a usefulness metric, not a filter.

Every abstraction below (`SourceSpecies`, the source protocol, the merge function, the `Result` summary) is shaped around this union-with-provenance model. If a future requirement wants "species seen in at least K sources", that is a *post-merge* filter over the provenance columns, not a change to how sources combine.

---

## 2. Architecture: one core service, five thin surfaces

```
                         generate_regional_taxa_list()   ← the only place the logic lives
                                     │
        ┌──────────────┬─────────────┼──────────────┬───────────────┐
   mgmt command    unit tests    admin action    DRF endpoint     main UI
 (+ --all-projects) (stub source) (Project/Site)  (POST …/regional/) (button → API)
```

Internally the service is a short pipeline:

```
region code ─▶ [Source clients]                 fetch_species() per source → list[SourceSpecies]
            ─▶ merge_source_species()            WIDE UNION on canonical key, provenance preserved
            ─▶ map_to_taxa()                     match/create Antenna Taxon rows
            ─▶ (optional) intersect_classifier() REPORT-ONLY coverage against a classifier's labels
            ─▶ save / update TaxaList            idempotent, project-scoped
            ─▶ Result                            counts + unmatched names for human review
```

**New module:** `ami/main/services/regional_taxa.py` (new `services` package under `ami/main/`, per the "processing logic extraction" note in `CLAUDE.md`; add `ami/main/services/__init__.py`).

**Reuses (do not reinvent):**
- `ami/utils/requests.py::create_session()` (`:14`) — all outbound HTTP, for retry/backoff.
- `ami/main/management/commands/import_taxa.py::create_taxon()` and `get_or_create_root_taxon()` — the rank-hierarchy builder for creating missing `Taxon` rows under the `Arthropoda` root. This logic currently lives inside the command module; see §5.3 for extracting it so the service can call it without importing a management command.
- `TaxaList.objects.get_or_create_for_project(name, project=None)` (`ami/main/models.py:4598`) — idempotent list creation, project-scoped.
- `AlgorithmCategoryMap.with_taxa()` (`ami/ml/models/algorithm.py:105`) — the name-keyed category→taxon resolution masking already uses; reused for the classifier-coverage report.
- `Project.objects.all()` loop shape from `ami/main/management/commands/assign_roles.py:79` — the `--all-projects` backfill template.

---

## 3. Data model changes

Minimal columns; polygons/geometry are explicitly out of scope (design doc Proposal C). Every field ships with its migration in the same PR (`makemigrations --check --dry-run` must pass — `CLAUDE.md` domain invariant).

### 3.1 `Site` (`ami/main/models.py:654`)

| Field | Type | Notes |
|---|---|---|
| `region_source` | `CharField(choices=RegionSource.choices, blank=True)` | `gbif_gadm` \| `inat_place`; blank = unset |
| `region_code` | `CharField(max_length=64, blank=True)` | a GADM GID (`USA.11_1`) or an iNat `place_id` string |
| `taxa_list` | `ForeignKey("TaxaList", null=True, blank=True, on_delete=SET_NULL, related_name="+")` | the designated list for this site |

### 3.2 `Project` (`ami/main/models.py:289`)

| Field | Type | Notes |
|---|---|---|
| `region_source` | `CharField(choices=RegionSource.choices, blank=True)` | fall-back source when a site has none |
| `region_code` | `CharField(max_length=64, blank=True)` | fall-back region code |
| `default_taxa_list` | `ForeignKey("TaxaList", null=True, blank=True, on_delete=SET_NULL, related_name="+")` | fall-back list when a site has none |

`RegionSource` is a `models.TextChoices` enum defined once (suggested home: `ami/main/models.py` near `TaxaList`, or a small `ami/main/services/regional_taxa.py` constant re-exported — keep the enum with the model so migrations reference a stable path).

**Relationship note.** `TaxaList↔Project` (`related_name="taxa_lists"`) and `TaxaList↔Taxon` (`related_name="lists"`) stay M2M. The new `taxa_list` / `default_taxa_list` are single FKs *layered on top*: a project still associates with many lists, but names one default. `related_name="+"` avoids reverse-accessor clutter on `TaxaList`.

**Migrations:** one migration in `ami/main/migrations/` adding all six fields (they are all additive, nullable/blank, no data change). If `Project` and `Site` edits are cleaner as two migrations, that is fine; either way they are state+schema migrations, not data migrations.

---

## 4. Source abstraction

### 4.1 `SourceSpecies` — the per-source record (the "wide table" row, pre-merge)

```python
# ami/main/services/regional_taxa.py
import dataclasses

@dataclasses.dataclass(frozen=True)
class SourceSpecies:
    """One species as reported by ONE source for a region.

    The merge step (§4.4) concatenates these across sources and deduplicates on a
    canonical key, unioning provenance. Fields are deliberately source-agnostic so
    a new source only has to populate what it knows.
    """
    source: str                      # RegionSource value, e.g. "gbif_gadm"
    scientific_name: str             # canonical binomial as the source spells it
    rank: str | None = None          # "SPECIES", "SUBSPECIES", … when the source gives it
    gbif_taxon_key: int | None = None
    inat_taxon_id: int | None = None
    observation_count: int | None = None   # source's record/observation count in the region
    raw: dict | None = None          # untouched source payload for debugging / future fields
```

### 4.2 The source protocol

```python
import typing

class RegionalSpeciesSource(typing.Protocol):
    source_key: str  # a RegionSource value

    def fetch_species(
        self, region_code: str, taxon_scope: "TaxonScope"
    ) -> list[SourceSpecies]:
        """Return every species the source records in `region_code`, within
        `taxon_scope` (e.g. Lepidoptera). Paginates internally; all HTTP goes
        through create_session(). Raises on transport/HTTP error — never returns
        a partial list silently (CLAUDE.md: raise, don't return sentinels)."""
```

`TaxonScope` is a tiny value object holding the source-specific root-taxon identifiers, so the caller says "Lepidoptera" once and each source translates it:

```python
@dataclasses.dataclass(frozen=True)
class TaxonScope:
    label: str                    # "Lepidoptera", for logging
    gbif_taxon_key: int | None    # e.g. 797 (Lepidoptera) — CANDIDATE, verify live
    inat_taxon_id: int | None     # e.g. 47157 (Lepidoptera) — CANDIDATE, verify live
```

Default scope: Lepidoptera (moth/butterfly platform). Keep it a parameter so a project could scope to Arthropoda or a family later.

### 4.3 Concrete sources (endpoints are CANDIDATE, UNVERIFIED)

No live GBIF/iNat code exists in `ami/` today — these fields are only ever populated from files. The endpoints below are from published API docs and must be exercised against the live services (a recorded-response fixture per source) before they are trusted. Rate limits and exact faceting behaviour are the first things to verify (§10, §11).

**`GBIFRegionalSource`** — GBIF occurrence search, faceted by species.
- Candidate endpoint: `GET https://api.gbif.org/v1/occurrence/search`
- Candidate params: `facet=speciesKey`, `facetLimit=<page>`, `facetOffset=<offset>`, `gadmGid=<region_code>` (or `country=<ISO2>` when the code is a country), `taxonKey=<Lepidoptera key>`, `hasCoordinate=true`, `limit=0` (we want facet buckets, not records).
- Pagination: page `facetOffset`/`facetLimit` until a facet page returns fewer than `facetLimit` buckets. GBIF caps facet depth, so very species-rich regions may need the "download" API instead — note as a known limit, not a v1 blocker.
- Each facet bucket gives a `speciesKey` and a count; resolve the key to a scientific name via `GET /v1/species/{speciesKey}` (batchable, cache per key). Populates `gbif_taxon_key`, `scientific_name`, `observation_count`.

**`INaturalistRegionalSource`** — iNat species counts by place.
- Candidate endpoint: `GET https://api.inaturalist.org/v1/observations/species_counts`
- Candidate params: `place_id=<region_code>`, `taxon_id=<Lepidoptera id>`, `quality_grade=research`, `per_page=200`, `page=<n>`.
- Pagination: increment `page` until `results` is short of `per_page` or `total_results` is reached.
- Each result has `taxon.id`, `taxon.name`, `taxon.rank`, `count`. Populates `inat_taxon_id`, `scientific_name`, `rank`, `observation_count`.

Both share an HTTP helper built on `create_session()`; add a small on-disk/Redis response cache keyed by `(source, region_code, taxon_scope)` because these queries are slow and rate-limited, and the same region is re-queried on every idempotent re-run. Cache TTL on the order of days is fine (regional checklists change slowly).

### 4.4 The wide merge — `merge_source_species()`

```python
def merge_source_species(
    per_source: list[list[SourceSpecies]],
) -> list["MergedSpecies"]:
    """Concatenate species across sources and deduplicate on a canonical key,
    UNIONING provenance. This is a wide join, never an intersection: a species in
    ANY source survives. Two source rows collapse into one MergedSpecies when they
    share a canonical key.

    Canonical key precedence (first that both rows share wins):
      1. gbif_taxon_key
      2. inat_taxon_id
      3. normalized scientific_name (casefold + collapse whitespace)
    """
```

```python
@dataclasses.dataclass
class MergedSpecies:
    scientific_name: str
    rank: str | None
    gbif_taxon_key: int | None
    inat_taxon_id: int | None
    sources: set[str]                       # provenance: which sources contributed
    observation_counts: dict[str, int]      # provenance: per-source count
    contributing: list[SourceSpecies]       # raw rows, for audit
```

Merge rules:
- **Dedup key** as above. Name-only collision without a shared external key is the fragile case — normalize (`casefold`, strip authorship if present, collapse whitespace) and, when two rows merge on name but disagree on an external key, keep both keys and log a provenance warning rather than silently dropping one.
- **Provenance union:** `sources = ∪ row.source`; `observation_counts[row.source] = row.observation_count`; keep both external keys if each source supplied one; prefer the GBIF name spelling when present, else the first.
- Output is stable-ordered (e.g. by `-max(observation_counts)`, then name) so runs are reproducible and diffs are readable.

---

## 5. Mapping merged species → Antenna `Taxon`

### 5.1 Match precedence — `map_to_taxa()`

```python
def map_to_taxa(
    merged: list[MergedSpecies], *, create_missing: bool, dry_run: bool,
) -> "MappingOutcome":
    """Resolve each MergedSpecies to a Taxon. Match precedence:
        1. Taxon.gbif_taxon_key == merged.gbif_taxon_key
        2. Taxon.inat_taxon_id == merged.inat_taxon_id
        3. Taxon.name == merged.scientific_name   (exact; Taxon.name is unique)
    On no match: create via the rank-hierarchy builder when create_missing, else
    record the name as unmatched for human review. Never mutate on dry_run."""
```

`MappingOutcome` carries: `matched: list[tuple[MergedSpecies, Taxon]]`, `created: list[Taxon]`, `unmatched_names: list[str]`. Do the external-key matches as two bulk `filter(..__in=[...])` queries (not per-row) — `CLAUDE.md`: no queries in loops.

### 5.2 The name-join coupling (why exact match matters here)

`Taxon.name` is globally unique (`models.py:4346`), and class masking joins list membership to classifier labels by **name** (`AlgorithmCategoryMap.with_taxa()`, keyed on `taxon.name` at `algorithm.py:135`). So:
- Matching a source species to an existing `Taxon` by external key and then trusting its `.name` is correct — the list stores `Taxon` rows, and masking will later match those same names to classifier labels.
- A source name that differs from both any `Taxon.name` and the classifier's label spelling will silently fail to mask even after we add it to the list. This is the **name-match fragility** open question (§10); the service surfaces `unmatched_names` and the classifier-coverage count precisely so a human can see the miss rate before trusting auto-masking.

### 5.3 Extract `create_taxon` for reuse

`create_taxon()` and `get_or_create_root_taxon()` live inside `ami/main/management/commands/import_taxa.py` today (module-level functions, so importable, but coupling the service to a command module is awkward). Extract them into `ami/main/services/taxonomy.py` (or a shared helper the command re-imports) so both the command and the new service call one implementation. This is a mechanical move-and-reimport; keep the command's behaviour identical and covered by its existing tests.

---

## 6. The core service function

```python
# ami/main/services/regional_taxa.py

@dataclasses.dataclass
class RegionalTaxaResult:
    region_source: str
    region_code: str
    taxa_list_id: int | None            # None on dry_run
    list_created: bool                  # False when an existing list was updated
    union_size: int                     # distinct species after the wide merge
    per_source_counts: dict[str, int]   # {"gbif_gadm": 812, "inat_place": 640}
    matched_existing: int               # merged species already present as a Taxon
    created_taxa: int                   # new Taxon rows created (0 when create_missing=False)
    in_classifier_labels: int | None    # coverage against classifier (None if no classifier given)
    not_in_classifier: int | None       # union_size - in_classifier_labels
    unmatched_names: list[str]          # source names with no Taxon and not created
    dry_run: bool


def generate_regional_taxa_list(
    *,
    region_source: str,
    region_code: str,
    project: "Project | None" = None,
    classifier: "Algorithm | None" = None,
    taxon_scope: TaxonScope | None = None,   # defaults to Lepidoptera
    sources: "list[RegionalSpeciesSource] | None" = None,  # defaults per region_source; DI seam for tests
    create_missing: bool = True,
    name: str | None = None,                 # defaults to f"{region_code} ({region_source})"
    dry_run: bool = False,
) -> RegionalTaxaResult:
    ...
```

Behaviour:
1. Resolve `sources` (default: the one client matching `region_source`; a caller may pass several to union). The `sources` parameter is the **dependency-injection seam** — tests pass a stubbed client, no HTTP.
2. `fetch_species()` each source → `merge_source_species()` → wide union.
3. `map_to_taxa(create_missing, dry_run)`.
4. If `classifier` given: compute coverage against its label set (reporting only) — reuse `classifier.category_map.with_taxa()` or a name-set intersection against the labels; do not filter the list by it.
5. Unless `dry_run`: `get_or_create_for_project(name, project)`, then set the list's taxa (idempotent — update the existing list's M2M rather than creating a duplicate, mirroring the manager's contract). `update_calculated_fields()` on the list if it has cached counts.
6. Return `RegionalTaxaResult`.

**Idempotency:** a second run for the same `(name, project)` updates the same `TaxaList` (the manager's `get_or_create_for_project` guarantees one row; the service replaces/refreshes its taxa set). Re-running never creates duplicate lists or duplicate `Taxon` rows (name-unique + external-key match handle that).

**No sentinels, no asserts:** failure paths raise (`CLAUDE.md`); the service returns a `RegionalTaxaResult` only on success. Callers translate exceptions to their surface (DRF 4xx, command error, admin message).

---

## 7. Region derivation (A3) — powers `--all-projects`

Most existing projects have no region code but do have deployment coordinates (`Deployment.latitude` `:770`, `longitude` `:771`). `derive_region_code()` reverse-geocodes a representative point to a region code so backfill needs no manual entry:

```python
def derive_region_code(
    project_or_site, *, region_source: str,
) -> str | None:
    """Reverse-geocode a representative deployment coordinate to a region code.
    Representative point = the centroid or first non-null (lat, lon) among the
    object's deployments (Site.boundary_rect() at models.py:670 already aggregates
    the extent). Returns None when no deployment has coordinates."""
```

- For `gbif_gadm`: candidate endpoint `GET https://api.gbif.org/v1/geocode/reverse?lat=<>&lng=<>` returning GADM GIDs (UNVERIFIED — confirm the response shape and which GADM level to take). Fall back to a bundled GADM lookup if the endpoint is unreliable.
- For `inat_place`: iNat has no clean reverse-geocode to a single place; prefer GBIF/GADM for derivation even when the chosen *fetch* source is iNat, or require manual `place_id` entry. Note this asymmetry.

A3 is what makes "backfill every known project" feasible: the `--all-projects` command path calls `derive_region_code()` when a project has no `region_code`, then `generate_regional_taxa_list()`. Whether derivation is reliable enough to run unattended is an explicit open verification item (§11) — until confirmed, `--all-projects` should default to `--dry-run` and print what it *would* create.

---

## 8. Auto-apply masking — resolution order

Extend `ClassMaskingConfig` (on branch `rework/999-class-masking-on-framework`, `ami/ml/post_processing/class_masking.py:17`) so the task can resolve the taxa list per occurrence instead of requiring an explicit `taxa_list_id`. **This change lands on the #999 branch (or a follow-up stacked on it), not on `main` today**, because `class_masking.py` does not exist on `main` yet.

### 8.1 Config change (additive, backwards-compatible)

Today `taxa_list_id: int` is required (`:25`). Make the list selection a discriminated choice so the explicit path is untouched:

```python
class ClassMaskingConfig(pydantic.BaseModel):
    source_image_collection_id: int | None = None
    occurrence_id: int | None = None
    algorithm_id: int
    reweight: bool = True

    # List selection: explicit id, OR auto-resolution per occurrence.
    taxa_list_id: int | None = None
    taxa_list_mode: typing.Literal["explicit", "auto"] = "explicit"

    @pydantic.root_validator(skip_on_failure=True)
    def _validate_list_selection(cls, values):
        if values["taxa_list_mode"] == "explicit" and values.get("taxa_list_id") is None:
            raise ValueError("explicit mode requires taxa_list_id")
        # auto mode ignores taxa_list_id and resolves per occurrence
        return values
```

Keep the existing `_exactly_one_scope` validator. The explicit path in `run()` (`class_masking.py:~305`, `TaxaList.objects.get(pk=config.taxa_list_id)`) is unchanged; a new `auto` branch resolves per occurrence.

### 8.2 Resolution order (from the design doc)

```
occurrence.deployment.research_site.taxa_list
  ↳ else research_site.region_code   → generate/lookup regional list
  ↳ else project.default_taxa_list
  ↳ else project.region_code         → generate/lookup regional list
  ↳ else no masking (log occurrence.pk and skip)
```

Implement as `resolve_taxa_list_for_occurrence(occurrence) -> TaxaList | None`, a helper (home: `ami/main/services/regional_taxa.py`, or a thin `ami/ml/post_processing/masking_resolution.py` that imports the service). When a step hits a `region_code` with no linked list, it calls `generate_regional_taxa_list()` (cache-backed, so it is cheap after the first run) and stores the result on the site/project so subsequent runs short-circuit to the FK.

**Batching (avoid N+1):** in `auto` mode, group the scoped occurrences by `(research_site, project)` first and resolve one list per group, not per occurrence — the scoped queryset is already built in `_scoped_classifications` (`class_masking.py:~280`). This keeps masking's existing batched-commit loop intact.

**Safety:** `auto` mode is a no-op when nothing resolves (log + skip), so a pipeline can enable it by default without masking projects that have no region/list configured. This preserves the existing explicit behaviour bit-for-bit for anyone still passing `taxa_list_id`.

### 8.3 How it plugs into the framework

The task is still triggered through the #1289 framework (`make_post_processing_action`, `ami/ml/post_processing/admin/actions.py:177`) and the admin form (`class_masking_form.py`). The form grows a "list mode" choice (explicit list dropdown vs. auto). The `build_jobs`/`default_build_jobs` path (`actions.py:87,184`) is unchanged — config still validates against `ClassMaskingConfig` before enqueue. Whether "auto" is a per-`ProjectPipelineConfig` toggle or a pipeline property is an open question (§10); the config-level `taxa_list_mode` is the minimum that unblocks manual/admin use.

---

## 9. The five surfaces (each a thin wrapper)

### 9.1 Management command — `ami/main/management/commands/generate_regional_taxa_list.py`
```
python manage.py generate_regional_taxa_list \
    --project <id> --region-source gbif_gadm --region <code> \
    [--classifier <algorithm_id>] [--scope lepidoptera] \
    [--no-create-missing] [--all-projects] [--dry-run]
```
- Single project: calls the service, prints the `RegionalTaxaResult` as a table.
- `--all-projects`: loops `Project.objects.all()` (shape from `assign_roles.py:79`); for each project without a `region_code`, calls `derive_region_code()` (A3); **defaults to `--dry-run`** until derivation reliability is confirmed (§11). Prints a per-project summary.
- Raises `CommandError` on failure; no sentinels.

### 9.2 Unit tests — call the service directly with a stubbed source
The primary regression surface (see §10). Stubbed `RegionalSpeciesSource` passed via the `sources=` DI seam; no network.

### 9.3 Django admin action — on `Project` and `Site` changelists
Built with `make_post_processing_action`-style plumbing is **not** required here (this is not a post-processing Job); instead a plain admin action + intermediate confirmation form (region source + code, optional classifier, dry-run checkbox) that calls the service and shows the `RegionalTaxaResult` via `messages`. Mirrors the confirmation-page pattern in `ami/ml/post_processing/admin/actions.py::render_confirmation` for consistency, but runs synchronously (regional fetch is slow — consider enqueuing a Job if it exceeds request timeout; note as a refinement).

### 9.4 DRF endpoint
`POST /api/v2/projects/{project_pk}/taxa-lists/regional/` as an `@action(detail=True, methods=["post"])` on `ProjectViewSet` (`ami/main/api/views.py:158`, already `ProjectMixin`), plus optionally a `Site` variant. Template: the `regroup_sessions` / `sync` actions (`views.py:339,363`) that validate, act, and return `202`.
- Body validated by a request serializer (`region_source`, `region_code`, optional `classifier_id`, `dry_run`); parse every param via `SingleParamSerializer` (`ami/base/serializers.py:108`) / a DRF serializer so bad input returns 400 not 500 (`CLAUDE.md` DoD).
- Permissions: `require_project`, object access through `get_object()`/`check_object_permissions()` — never a raw pk lookup (`CLAUDE.md` DoD). Only project members with the right role may generate (align with membership model; §11 verification item).
- Because a live fetch is slow, the endpoint should enqueue a Job and return `{"job_id": …}` (like `sync`), with `dry_run` running synchronously for preview. Decide sync-vs-async here explicitly.

### 9.5 Main UI button — later slice
"Create taxa list for region" in Project settings and the Site editor, calling 9.4. Reference the closed **#1020** GBIF taxon-select React component for the region/place picker. Add a React Query mutation hook under `ui/src/data-services/hooks/` (follow `ui/AGENTS.md`). Explicitly a **later phase** (§Phase 4).

---

## 10. Test plan (TDD — write these first)

All tests use factories (`ami/*/tests/factories.py`) and the stubbed-source DI seam; **no test hits a live API**. Record one real GBIF and one real iNat response as a fixture (small, scrubbed) for the source-client parsing tests.

1. **Source-client parsing** — feed each concrete source a recorded/canned JSON payload (monkeypatched `create_session`/response) and assert it yields the expected `SourceSpecies` list, including pagination termination and key/name/count extraction. One test per source.
2. **Wide merge — union + provenance** (the load-bearing test for the core decision):
   - Two sources sharing a species by `gbif_taxon_key` collapse to one `MergedSpecies` with `sources == {both}` and both counts.
   - A species in only one source survives (union, not intersection).
   - Name-only collision with conflicting external keys keeps both keys and logs a warning.
   - Dedup-key precedence (gbif → inat → name) exercised explicitly.
3. **Mapping + create** — existing `Taxon` matched by external key; matched by name; `create_missing=True` creates via the hierarchy builder; `create_missing=False` records `unmatched_names`. Assert no duplicate `Taxon` on re-run (name-unique).
4. **Idempotency** — run the service twice for the same `(name, project)`; assert one `TaxaList`, taxa set refreshed, no duplicate lists/taxa.
5. **Classifier coverage is report-only** — with a `classifier`, assert `in_classifier_labels` / `not_in_classifier` are populated and that the saved list's taxa are **not** filtered by the classifier (a species outside the classifier's labels still appears in the list).
6. **Region derivation (A3)** — `derive_region_code()` returns a code for a project with deployment coords (stubbed reverse-geocode) and `None` when no deployment has coordinates.
7. **Masking resolution order** — parametrize the five-step ladder: site list wins over site region-code wins over project default list wins over project region-code wins over skip. Assert `auto` mode is a no-op (skips, does not raise) when nothing resolves, and that explicit `taxa_list_id` still behaves exactly as before.
8. **Masking `auto` batching** — `assertNumQueries` with a **multi-row** fixture (occurrences across two sites) proving list resolution is grouped, not per-occurrence (single-row fixtures cannot catch N+1 — `CLAUDE.md` DoD; template `ami/ml/tests.py:1006`). Strict `==` counts.
9. **Endpoint permission matrix** — member / non-member / anonymous / superuser against `POST …/regional/` (template `ami/main/tests.py:1532`); `?…=abc` bad-param returns 400.
10. **Command** — `--dry-run` creates nothing; `--all-projects --dry-run` iterates and reports; failure raises `CommandError`.

Repo rules to honour while writing: migration in the same PR; no `assert` in production code; raise don't return sentinels; test docstrings state the invariant, not "this PR added X".

---

## 11. Phased rollout (internal-first)

Order the slices so the internal path is usable and validated before the API/UI. Each phase is independently shippable and mergeable.

**Phase 0 — De-risk the external APIs (spike, no merge).**
Exercise the candidate GBIF and iNat endpoints from a scratch script against 2–3 real regions (one where a project already exists — e.g. Quebec/Vermont for the moths classifier). Confirm: faceting/pagination behaviour, rate limits, name/key/count fields, and reverse-geocode response shape. **Gate:** measure how many of a real classifier's labels a generated regional list actually covers (the design doc's key unknown). This decides whether Proposal A is useful alone or needs Proposal B's manual curation. Output: a short findings note + recorded response fixtures for the parsing tests. *De-risks: the whole premise (coverage) and every "CANDIDATE, UNVERIFIED" endpoint above.*

**Phase 1 — Core service + one source + model fields (backend, no UI).**
`SourceSpecies`/`MergedSpecies`/protocol, one concrete source (whichever won Phase 0 on moth coverage), `merge_source_species`, `map_to_taxa`, `generate_regional_taxa_list`, the `Site`/`Project` fields + migration, and `create_taxon` extraction (§5.3). Tests 1–5. *De-risks: the union-with-provenance core and the data model, behind unit tests, with zero external dependency in CI.*

**Phase 2 — Management command + admin action + A3.**
Command (incl. `--all-projects --dry-run` backfill), `derive_region_code`, admin actions on Project/Site. Tests 6, 10. *De-risks: unattended backfill and gives internal users a way to generate lists before any API exists.*

**Phase 3 — Masking auto-resolution (on the #999 branch / stacked follow-up).**
`ClassMaskingConfig` `taxa_list_mode`, resolution ladder, batched grouping, admin form "list mode". Tests 7, 8. **Requires #999 to have landed or be the base branch** — coordinate with that PR. *De-risks: the "works out of the box" promise; gated behind no-op-when-unconfigured so it is safe to enable.*

**Phase 4 — API endpoint + main UI.**
`POST …/regional/` (sync-vs-async decided), request serializer, permission matrix (test 9), then the React button reusing #1020's picker. *De-risks: external/self-serve use once the service output is trusted internally.*

Second source (union path) can slot in whenever Phase 0 shows it adds coverage — the merge already supports it; adding a source is `+1` client + `+1` parsing test.

---

## 12. Open questions (carried from the design doc + implementation-level)

Design-doc decisions still open:
- **GBIF vs iNaturalist first** — decided empirically in Phase 0 by moth coverage + key cleanliness.
- **GADM granularity** — level 1 (state/province) vs level 2 (county). Make it configurable per site/project; default level 1, revisit after Phase 0.
- **Create-vs-skip unmatched taxa** — exposed as `create_missing` (default True). Confirm we want to grow the taxonomy from external sources vs. only intersect with existing taxa.
- **TaxaList scope** — regional lists are project-scoped (not global) so one project's region does not pollute another's picker. Confirmed direction; `get_or_create_for_project(project=...)`.
- **How the pipeline auto-applies masking** — per-`ProjectPipelineConfig` toggle vs. pipeline property. `taxa_list_mode="auto"` at the config level is the minimum; the pipeline-wiring decision aligns with #1289/#999.
- **Name-match fragility** — masking joins on `Taxon.name`; source/classifier spelling mismatches silently drop species. Measured in Phase 0; surfaced per-run via `unmatched_names` + `not_in_classifier`.

Implementation-level questions surfaced here:
- **Sync vs. async for the endpoint/admin action** — regional fetch can exceed request timeouts; likely enqueue a Job (like `sync`), keep `dry_run` synchronous. Decide in Phase 2/4.
- **Cache backend + TTL** for source responses (Redis vs. on-disk; days-scale TTL). Needed once real fetch latency is known (Phase 0).
- **Where `RegionSource` and the masking-resolution helper live** — enum with the model (stable migration path); resolver in `services/` vs. a thin `ml/post_processing/` shim.
- **Reverse-geocode reliability for unattended backfill** — until confirmed, `--all-projects` stays `--dry-run` by default (§7).

## 13. What we still need to verify before building

- Exact GBIF endpoint + params returning a species list for a GADM region, its facet-depth cap, and rate limits — and the iNat equivalent (`species_counts` by `place_id`). Both are on-paper only.
- The GBIF reverse-geocode response shape and which GADM level to take for A3.
- Label-coverage of a generated regional list against a **real** classifier (Quebec/Vermont moths) — the go/no-go for Proposal A standing alone.
- Permissions story for the new fields and the generate action (who may set a region, who may trigger generation) consistent with the project-membership model.
```
