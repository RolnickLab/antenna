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

Proposal A adds one capability — **"given a region, produce a taxa list"** — written once as a service function and surfaced five ways (management command, unit test, Django admin action, DRF endpoint, main UI). It fetches the species recorded in a geographic region from one or more external biodiversity databases (GBIF, iNaturalist), maps them onto Antenna `Taxon` rows, restricts (by default) to the species some classifier can actually predict, and saves a project-scoped `TaxaList`. It also adds region/list fields to `Site` and `Project` and a resolution order so the class-masking task can pick the right list automatically per occurrence.

### 1.1 The one design decision to get right: multiple sources UNION, they do not INTERSECT

When more than one source is queried (GBIF **and** iNaturalist, say), a species present in **any** source is a candidate for the regional list. The sources are combined with a **wide join / concatenation**, not an intersection:

- The merged intermediate is a **wide table**: one row per canonical species, carrying per-source provenance columns — which source(s) contributed the species, each source's native key (`gbif_taxon_key`, `inat_taxon_id`, …), and each source's observation count.
- Sources are **never intersected against each other**. Querying two sources can only grow the candidate set, never shrink it.
- The **only** intersections in the whole flow are applied *after* the union and are separate axes from source provenance: (i) an *optional, reporting-only* comparison against one specific classifier's label set, and (ii) the **model-coverage** restriction described in §6 (does any classifier cover this species at all). Neither removes species based on which source they came from; they act on the taxon after mapping. See §6 for how model-coverage is a separate axis from source provenance.

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
            ─▶ apply_model_coverage()            annotate/subset by classifier coverage (§6)
            ─▶ (optional) intersect_classifier() REPORT-ONLY coverage against ONE named classifier
            ─▶ save / update TaxaList            idempotent, project-scoped
            ─▶ Result                            bucketed counts + unmatched names for human review
```

**New module:** `ami/main/services/regional_taxa.py` (new `services` package under `ami/main/`, per the "processing logic extraction" note in `CLAUDE.md`; add `ami/main/services/__init__.py`).

**Reuses (do not reinvent):**
- `ami/utils/requests.py::create_session()` (`:14`) — all outbound HTTP, for retry/backoff.
- `ami/main/management/commands/import_taxa.py::create_taxon()` and `get_or_create_root_taxon()` — the rank-hierarchy builder for creating missing `Taxon` rows under the `Arthropoda` root. This logic currently lives inside the command module; see §5.3 for extracting it so the service can call it without importing a management command.
- `TaxaList.objects.get_or_create_for_project(name, project=None)` (`ami/main/models.py:4598`) — idempotent list creation, project-scoped.
- `AlgorithmCategoryMap.with_taxa()` (`ami/ml/models/algorithm.py:105`) — the name-keyed category→taxon resolution masking already uses; reused for both the classifier-coverage report and the persisted model-coverage relationship (§6).
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

### 3.3 Model-coverage relationship (the "are the models aware of this taxon" field)

This is the persisted relationship required by §6. Storing it here (not computing it live) is a deliberate decision — see §6.2 for the options considered and the recommendation.

- **`Taxon.covered_by_algorithms`** — `ManyToManyField("ml.Algorithm", related_name="covered_taxa", blank=True)`. The persisted through-relationship: which classifier(s) can predict this taxon, i.e. whose category-map label set contains the taxon's name (the same name-match `with_taxa()` uses). This is what lets the list/UI show *which* model is aware of a taxon, not just whether one is.
- **`Taxon.has_model_coverage`** — `BooleanField(default=False, db_index=True)`. Denormalized flag: `True` iff `covered_by_algorithms` is non-empty. Gives cheap filtering and a simple UI badge without a join. Acceptable as the MVP on its own if the M2M is deferred (see §6.2).

"Which algorithm(s) cover this taxon" is then a direct read — `taxon.covered_by_algorithms.all()` — and "which taxa can this model predict" is `algorithm.covered_taxa.all()`.

**Implementation note (dedup):** because many `Algorithm` rows share one `category_map` (the FK at `ami/ml/models/algorithm.py:212`), the refresh (§6.3) computes membership once per *category map* from its label set and then fans it out to the algorithms that use that map. Whether the persisted M2M is materialized directly as `Taxon ↔ Algorithm` (more rows, direct read) or normalized as `Taxon ↔ AlgorithmCategoryMap` with algorithm-level answers derived via the FK is left as an open question (§13); the recommended default is the direct `Taxon ↔ Algorithm` relationship the user asked for.

**Migrations:** the M2M through table is an `ami/ml`-or-`ami/main` migration (either app can host a `Taxon ↔ Algorithm` M2M — put it where `Taxon` lives, `ami/main`, referencing `ml.Algorithm`); the `has_model_coverage` boolean is an `ami/main/` migration on `Taxon`. Both are additive. Neither backfills automatically — the refresh command (§6.3) populates them, and the same migration PR should either run a data migration calling that refresh or document that the command must be run once after deploy.

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

No live GBIF/iNat code exists in `ami/` today — these fields are only ever populated from files. The endpoints below are from published API docs and must be exercised against the live services (a recorded-response fixture per source) before they are trusted. Rate limits and exact faceting behaviour are the first things to verify (see Phase 0, §12, and §14).

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

Note that model-coverage (§6) is **not** part of the merge — it is applied after mapping to `Taxon`, as a separate axis. Merging is only about combining sources.

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
- A source name that differs from both any `Taxon.name` and the classifier's label spelling will silently fail to mask even after we add it to the list. This is the **name-match fragility** open question (§13); the service surfaces `unmatched_names`, the model-coverage buckets (§6), and the classifier-coverage count precisely so a human can see the miss rate before trusting auto-masking.

Because model-coverage (§6) is keyed on the same name-match, a mapped `Taxon` and its coverage flag are consistent with what masking will actually do at run time, by construction.

### 5.3 Extract `create_taxon` for reuse

`create_taxon()` and `get_or_create_root_taxon()` live inside `ami/main/management/commands/import_taxa.py` today (module-level functions, so importable, but coupling the service to a command module is awkward). Extract them into `ami/main/services/taxonomy.py` (or a shared helper the command re-imports) so both the command and the new service call one implementation. This is a mechanical move-and-reimport; keep the command's behaviour identical and covered by its existing tests.

---

## 6. Model & DB awareness

The generator must be aware of two things about every candidate species before it saves a list:

- **DB presence** — does a `Taxon` row already exist (matched by external key or name, §5.1)?
- **Model coverage** — is the taxon covered by at least one classifier, i.e. does its name appear in some `AlgorithmCategoryMap` label set (the same `Taxon.name == label` join class masking uses)?

These two facts drive the default behaviour, the opt-in richer behaviour, and the `Result` breakdown. Model-coverage is a **separate axis** from source provenance (§1.1): the wide merge still unions all sources; coverage is applied afterwards, per mapped `Taxon`. Do not conflate "in multiple sources" with "model-aware" — they are orthogonal.

### 6.1 Default subsets to model-known species; opt-in creates the rest, flagged

- **Default:** the saved list is `regional-species-from-sources ∩ taxa-covered-by-at-least-one-classifier`. Rationale: class masking can only ever affect taxa in some classifier's label set, so a regional species no model can predict is inert for masking. Keeping the default tight makes the list predictable and keeps "why does my 1500-species region only mask to N" answerable.
- **Opt-in (`include_uncovered=True`, exposed as `--include-uncovered` / a form checkbox):** also keep regional species with no model coverage. Under this mode, species absent from the DB are created via the hierarchy builder (§5.3) but each carries an honest coverage indicator — `has_model_coverage=False` and an empty `covered_by_algorithms` — so the list/UI can show "in the region, but no model can predict it yet". Many valid regional species have no training data and will never appear in a prediction list; the model must not pretend otherwise.

A note on interaction with `create_missing` (§5.1): under the default (model-covered-only) scope, a species is kept only if its name matches some label set; creating its `Taxon` when missing is safe because, by construction, it *is* classifiable. Under `include_uncovered`, `create_missing` also governs whether uncovered species get `Taxon` rows created (default yes) or are only reported as unmatched.

### 6.2 The persisted relationship — options and recommendation

Confirmed by code reading: there is **no persisted `Taxon ↔ Algorithm` or `Taxon ↔ AlgorithmCategoryMap` link today**. `Algorithm.category_map` is an FK to `AlgorithmCategoryMap` (`ami/ml/models/algorithm.py:212`, `related_name="algorithms"`); the label set lives in `data` (JSON) + `labels` (`ArrayField`) with a `labels_hash` BigInt; and the only label→`Taxon` path is `with_taxa()` (`algorithm.py:105`), which resolves names **on the fly, unpersisted**. So a persisted relationship has to be added — the user explicitly wants "a field relationship to show if the models are aware of them", not a live computation.

| Option | Shape | Verdict |
|---|---|---|
| (a) boolean | `Taxon.has_model_coverage` denorm, refreshed on category-map change | Cheap, filterable, good UI badge — but cannot say *which* model covers a taxon. Acceptable **MVP** on its own. |
| (b) through relationship | persisted `Taxon.covered_by_algorithms` M2M → `Algorithm` | Answers "which model(s) cover this taxon", supports per-classifier questions. The user asked for a relationship → this is the **target**. |
| (c) compute-only | keep using `with_taxa()` live, no schema | Cheapest, but no persisted field and slow to filter/UI. **Rejected** — it is exactly today's state, and the user wants persistence. |

**Recommendation: (b), the direct `Taxon ↔ Algorithm` M2M (`covered_by_algorithms`), plus (a) `has_model_coverage` as a denormalized convenience.** The M2M reads directly — `taxon.covered_by_algorithms.all()` names the covering models with no join — which is exactly the "show which models are aware" capability the user asked for. The boolean rides alongside for cheap filtering and a simple "models know this species" badge. To avoid recomputing per algorithm (many share one `category_map`), the refresh resolves membership once per category map and fans it out to that map's algorithms (§3.3, §6.3). Whether to instead normalize as `Taxon ↔ AlgorithmCategoryMap` (fewer rows when maps are shared, algorithm answers derived via the FK) is an open question (§13); the recommended default stays the direct through-model.

If (b) is too much for the first slice, ship (a) alone as the MVP (boolean only), and add the M2M in a follow-up — the service and `Result` treat coverage as a single predicate either way, so the upgrade does not change their contract.

### 6.3 Refresh / consistency — coverage is derived data

Classifier label sets change whenever an algorithm or category map is added or updated, so model-coverage is derived and needs an explicit refresh path tied to the same name-resolution `with_taxa()` uses (so coverage always matches masking's join):

- **`refresh_algorithm_coverage(algorithm)`** — resolve the taxa for the algorithm's `category_map` label set once via the `with_taxa()` resolution, set `algorithm.covered_taxa` to that set, then update `Taxon.has_model_coverage` for the affected taxa (True iff `covered_by_algorithms` is still non-empty). Because algorithms sharing a `category_map` resolve to the same taxa, the label→taxa resolution is done per map and fanned out to each algorithm using it. Set-based, bulk, no per-row queries.
- **Hook on change:** recompute on `AlgorithmCategoryMap` save/import when the label set changes. `labels_hash` (`algorithm.py:68`) is the ready-made "did the label set change" signal — compare before/after and only recompute when it moves. Also trigger on the algorithm-registration / category-map-import code path that first creates a map.
- **Full rebuild:** a management command `refresh_taxon_model_coverage` loops all category maps / algorithms, rebuilds the `covered_by_algorithms` membership, and recomputes `has_model_coverage` — used for the initial backfill (the migration in §3.3) and as a repair tool.
- **When it recomputes** is called out explicitly so readers are not surprised by staleness: on category-map create/update (hook), and on demand (command). It is *not* recomputed on every occurrence write — masking still resolves names live via `with_taxa()`, so a brief lag in the denormalized flag never causes a wrong mask, only a slightly stale `has_model_coverage` badge until the next refresh.

### 6.4 How the service uses coverage

In `generate_regional_taxa_list()` (§7): after `map_to_taxa()`, `apply_model_coverage()` partitions the mapped taxa into model-covered vs. uncovered using the persisted `has_model_coverage` / `covered_by_algorithms` relationship (not a live recompute — the relationship is the source of truth, kept fresh by §6.3). The default scope keeps only the covered partition; `include_uncovered` keeps both. The optional `classifier=` argument is a *narrower, reporting-only* overlay on top: "of the kept species, how many are in *this specific* model's labels" — it never changes which taxa are saved.

---

## 7. The core service function

```python
# ami/main/services/regional_taxa.py

@dataclasses.dataclass
class RegionalTaxaResult:
    region_source: str
    region_code: str
    taxa_list_id: int | None            # None on dry_run
    list_created: bool                  # False when an existing list was updated
    # --- source union (§1.1) ---
    regional_total: int                 # distinct species after the wide merge (union across sources)
    per_source_counts: dict[str, int]   # {"gbif_gadm": 812, "inat_place": 640}
    # --- DB presence & model coverage (§6) ---
    already_in_db: int                  # merged species already present as a Taxon
    created_taxa: int                   # new Taxon rows created this run
    model_covered: int                  # kept by default: covered by >=1 classifier
    regional_no_model_coverage: int     # in region but no model covers them
                                        #   (created+flagged under include_uncovered, else skipped)
    saved_list_size: int                # taxa actually written to the TaxaList
    # --- optional single-classifier report (§6.4) ---
    in_classifier_labels: int | None    # coverage vs the ONE classifier passed (None if none given)
    not_in_classifier: int | None       # saved_list_size - in_classifier_labels
    # --- review ---
    unmatched_names: list[str]          # source names with no Taxon and not created
    dry_run: bool


def generate_regional_taxa_list(
    *,
    region_source: str,
    region_code: str,
    project: "Project | None" = None,
    classifier: "Algorithm | None" = None,       # OPTIONAL single-model report only (§6.4)
    taxon_scope: TaxonScope | None = None,       # defaults to Lepidoptera
    sources: "list[RegionalSpeciesSource] | None" = None,  # defaults per region_source; DI seam for tests
    include_uncovered: bool = False,             # default subsets to model-covered species (§6.1)
    create_missing: bool = True,
    name: str | None = None,                     # defaults to f"{region_code} ({region_source})"
    dry_run: bool = False,
) -> RegionalTaxaResult:
    ...
```

Behaviour:
1. Resolve `sources` (default: the one client matching `region_source`; a caller may pass several to union). The `sources` parameter is the **dependency-injection seam** — tests pass a stubbed client, no HTTP.
2. `fetch_species()` each source → `merge_source_species()` → wide union (`regional_total`).
3. `map_to_taxa(create_missing, dry_run)` → matched/created/unmatched (`already_in_db`, `created_taxa`, `unmatched_names`).
4. `apply_model_coverage()` (§6.4): partition mapped taxa into covered / uncovered via the persisted relationship (`model_covered`, `regional_no_model_coverage`). Default keeps covered only; `include_uncovered` keeps both (creating + flagging uncovered per §6.1).
5. If `classifier` given: compute the single-model report against its label set (reporting only) — reuse `classifier.category_map.with_taxa()` or a name-set intersection against the labels; do not filter the list by it.
6. Unless `dry_run`: `get_or_create_for_project(name, project)`, then set the list's taxa (idempotent — update the existing list's M2M rather than creating a duplicate, mirroring the manager's contract). `update_calculated_fields()` on the list if it has cached counts.
7. Return `RegionalTaxaResult`.

**Idempotency:** a second run for the same `(name, project)` updates the same `TaxaList` (the manager's `get_or_create_for_project` guarantees one row; the service replaces/refreshes its taxa set). Re-running never creates duplicate lists or duplicate `Taxon` rows (name-unique + external-key match handle that).

**No sentinels, no asserts:** failure paths raise (`CLAUDE.md`); the service returns a `RegionalTaxaResult` only on success. Callers translate exceptions to their surface (DRF 4xx, command error, admin message).

---

## 8. Region derivation (A3) — powers `--all-projects`

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

A3 is what makes "backfill every known project" feasible: the `--all-projects` command path calls `derive_region_code()` when a project has no `region_code`, then `generate_regional_taxa_list()`. Whether derivation is reliable enough to run unattended is an explicit open verification item (§14) — until confirmed, `--all-projects` should default to `--dry-run` and print what it *would* create.

---

## 9. Auto-apply masking — resolution order

Extend `ClassMaskingConfig` (on branch `rework/999-class-masking-on-framework`, `ami/ml/post_processing/class_masking.py:17`) so the task can resolve the taxa list per occurrence instead of requiring an explicit `taxa_list_id`. **This change lands on the #999 branch (or a follow-up stacked on it), not on `main` today**, because `class_masking.py` does not exist on `main` yet.

### 9.1 Config change (additive, backwards-compatible)

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

### 9.2 Resolution order (from the design doc)

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

### 9.3 How it plugs into the framework

The task is still triggered through the #1289 framework (`make_post_processing_action`, `ami/ml/post_processing/admin/actions.py:177`) and the admin form (`class_masking_form.py`). The form grows a "list mode" choice (explicit list dropdown vs. auto). The `build_jobs`/`default_build_jobs` path (`actions.py:87,184`) is unchanged — config still validates against `ClassMaskingConfig` before enqueue. Whether "auto" is a per-`ProjectPipelineConfig` toggle or a pipeline property is an open question (§13); the config-level `taxa_list_mode` is the minimum that unblocks manual/admin use.

---

## 10. The five surfaces (each a thin wrapper)

### 10.1 Management command — `ami/main/management/commands/generate_regional_taxa_list.py`
```
python manage.py generate_regional_taxa_list \
    --project <id> --region-source gbif_gadm --region <code> \
    [--classifier <algorithm_id>] [--scope lepidoptera] \
    [--include-uncovered] [--no-create-missing] [--all-projects] [--dry-run]
```
- Single project: calls the service, prints the `RegionalTaxaResult` bucket breakdown as a table (regional-total / already-in-db / model-covered / no-model-coverage / saved).
- `--all-projects`: loops `Project.objects.all()` (shape from `assign_roles.py:79`); for each project without a `region_code`, calls `derive_region_code()` (A3); **defaults to `--dry-run`** until derivation reliability is confirmed (§14). Prints a per-project summary.
- Raises `CommandError` on failure; no sentinels.

A sibling command `refresh_taxon_model_coverage` (§6.3) rebuilds the coverage relationship + `has_model_coverage`; it is independent of region generation but shares the coverage plumbing.

### 10.2 Unit tests — call the service directly with a stubbed source
The primary regression surface (see §11). Stubbed `RegionalSpeciesSource` passed via the `sources=` DI seam; no network.

### 10.3 Django admin action — on `Project` and `Site` changelists
Built with `make_post_processing_action`-style plumbing is **not** required here (this is not a post-processing Job); instead a plain admin action + intermediate confirmation form (region source + code, optional classifier, include-uncovered, dry-run checkbox) that calls the service and shows the `RegionalTaxaResult` via `messages`. Mirrors the confirmation-page pattern in `ami/ml/post_processing/admin/actions.py::render_confirmation` for consistency, but runs synchronously (regional fetch is slow — consider enqueuing a Job if it exceeds request timeout; note as a refinement).

### 10.4 DRF endpoint
`POST /api/v2/projects/{project_pk}/taxa-lists/regional/` as an `@action(detail=True, methods=["post"])` on `ProjectViewSet` (`ami/main/api/views.py:158`, already `ProjectMixin`), plus optionally a `Site` variant. Template: the `regroup_sessions` / `sync` actions (`views.py:339,363`) that validate, act, and return `202`.
- Body validated by a request serializer (`region_source`, `region_code`, optional `classifier_id`, `include_uncovered`, `dry_run`); parse every param via `SingleParamSerializer` (`ami/base/serializers.py:108`) / a DRF serializer so bad input returns 400 not 500 (`CLAUDE.md` DoD).
- Permissions: `require_project`, object access through `get_object()`/`check_object_permissions()` — never a raw pk lookup (`CLAUDE.md` DoD). Only project members with the right role may generate (align with membership model; §14 verification item).
- Because a live fetch is slow, the endpoint should enqueue a Job and return `{"job_id": …}` (like `sync`), with `dry_run` running synchronously for preview. Decide sync-vs-async here explicitly.

### 10.5 Main UI button — later slice
"Create taxa list for region" in Project settings and the Site editor, calling 10.4. Reference the closed **#1020** GBIF taxon-select React component for the region/place picker. Add a React Query mutation hook under `ui/src/data-services/hooks/` (follow `ui/AGENTS.md`). Explicitly a **later phase** (§12 Phase 4). The list detail/UI should surface the model-coverage flag so uncovered species are visibly marked (§6.1).

---

## 11. Test plan (TDD — write these first)

All tests use factories (`ami/*/tests/factories.py`) and the stubbed-source DI seam; **no test hits a live API**. Record one real GBIF and one real iNat response as a fixture (small, scrubbed) for the source-client parsing tests.

1. **Source-client parsing** — feed each concrete source a recorded/canned JSON payload (monkeypatched `create_session`/response) and assert it yields the expected `SourceSpecies` list, including pagination termination and key/name/count extraction. One test per source.
2. **Wide merge — union + provenance** (the load-bearing test for the core decision):
   - Two sources sharing a species by `gbif_taxon_key` collapse to one `MergedSpecies` with `sources == {both}` and both counts.
   - A species in only one source survives (union, not intersection).
   - Name-only collision with conflicting external keys keeps both keys and logs a warning.
   - Dedup-key precedence (gbif → inat → name) exercised explicitly.
3. **Mapping + create** — existing `Taxon` matched by external key; matched by name; `create_missing=True` creates via the hierarchy builder; `create_missing=False` records `unmatched_names`. Assert no duplicate `Taxon` on re-run (name-unique).
4. **Idempotency** — run the service twice for the same `(name, project)`; assert one `TaxaList`, taxa set refreshed, no duplicate lists/taxa.
5. **Single-classifier coverage is report-only** — with a `classifier`, assert `in_classifier_labels` / `not_in_classifier` are populated and that the saved list's taxa are **not** filtered by that classifier beyond the default model-coverage rule.
6. **Model-coverage default subset (§6.1)** — a region whose species are a mix of model-covered and uncovered: default run saves only the covered ones; `Result.model_covered` and `regional_no_model_coverage` buckets are correct; an uncovered species is absent from the saved list.
7. **Opt-in create-and-flag (§6.1)** — with `include_uncovered=True`, uncovered regional species are kept, their `Taxon` rows created (under `create_missing`), and each is flagged `has_model_coverage=False` with an empty `covered_by_algorithms`. Assert the covered species remain flagged `True`.
8. **Coverage refresh (§6.3)** — adding a category map whose labels match a taxon sets that taxon's `has_model_coverage=True` and its `covered_by_algorithms` membership; removing/renaming the label (changing `labels_hash`) drops coverage on the next refresh; `taxon.covered_by_algorithms.all()` returns the covering algorithm(s). Exercise both the hook and the `refresh_taxon_model_coverage` command.
9. **Region derivation (A3)** — `derive_region_code()` returns a code for a project with deployment coords (stubbed reverse-geocode) and `None` when no deployment has coordinates.
10. **Masking resolution order (§9.2)** — parametrize the five-step ladder: site list wins over site region-code wins over project default list wins over project region-code wins over skip. Assert `auto` mode is a no-op (skips, does not raise) when nothing resolves, and that explicit `taxa_list_id` still behaves exactly as before.
11. **Masking `auto` batching** — `assertNumQueries` with a **multi-row** fixture (occurrences across two sites) proving list resolution is grouped, not per-occurrence (single-row fixtures cannot catch N+1 — `CLAUDE.md` DoD; template `ami/ml/tests.py:1006`). Strict `==` counts.
12. **Endpoint permission matrix** — member / non-member / anonymous / superuser against `POST …/regional/` (template `ami/main/tests.py:1532`); `?…=abc` bad-param returns 400.
13. **Command** — `--dry-run` creates nothing; `--all-projects --dry-run` iterates and reports; failure raises `CommandError`.

Repo rules to honour while writing: migration in the same PR; no `assert` in production code; raise don't return sentinels; test docstrings state the invariant, not "this PR added X".

---

## 12. Phased rollout (internal-first)

Order the slices so the internal path is usable and validated before the API/UI. Each phase is independently shippable and mergeable.

**Phase 0 — De-risk the external APIs (spike, no merge).**
Exercise the candidate GBIF and iNat endpoints from a scratch script against 2–3 real regions (one where a project already exists — e.g. Quebec/Vermont for the moths classifier). Confirm: faceting/pagination behaviour, rate limits, name/key/count fields, and reverse-geocode response shape. **Gate:** measure how many of a real classifier's labels a generated regional list actually covers (the design doc's key unknown). This decides whether Proposal A is useful alone or needs Proposal B's manual curation. Output: a short findings note + recorded response fixtures for the parsing tests. *De-risks: the whole premise (coverage) and every "CANDIDATE, UNVERIFIED" endpoint above.*

**Phase 1 — Core service + one source + model fields + coverage relationship (backend, no UI).**
`SourceSpecies`/`MergedSpecies`/protocol, one concrete source (whichever won Phase 0 on moth coverage), `merge_source_species`, `map_to_taxa`, `apply_model_coverage`, `generate_regional_taxa_list`, the `Site`/`Project` fields + migration, the **model-coverage relationship (`covered_by_algorithms` + `has_model_coverage`) + refresh hook/command (§3.3, §6)**, and `create_taxon` extraction (§5.3). Tests 1–8. *De-risks: the union-with-provenance core, the data model, and the "are the models aware" relationship, behind unit tests with zero external dependency in CI. The coverage relationship is Phase-1 material because the default list behaviour depends on it.*

**Phase 2 — Management command + admin action + A3.**
Command (incl. `--all-projects --dry-run` backfill), `derive_region_code`, admin actions on Project/Site. Tests 9, 13. *De-risks: unattended backfill and gives internal users a way to generate lists before any API exists.*

**Phase 3 — Masking auto-resolution (on the #999 branch / stacked follow-up).**
`ClassMaskingConfig` `taxa_list_mode`, resolution ladder, batched grouping, admin form "list mode". Tests 10, 11. **Requires #999 to have landed or be the base branch** — coordinate with that PR. *De-risks: the "works out of the box" promise; gated behind no-op-when-unconfigured so it is safe to enable.*

**Phase 4 — API endpoint + main UI.**
`POST …/regional/` (sync-vs-async decided), request serializer, permission matrix (test 12), then the React button reusing #1020's picker and surfacing the model-coverage flag. *De-risks: external/self-serve use once the service output is trusted internally.*

Second source (union path) can slot in whenever Phase 0 shows it adds coverage — the merge already supports it; adding a source is `+1` client + `+1` parsing test.

---

## 13. Open questions (carried from the design doc + implementation-level)

Design-doc decisions still open:
- **GBIF vs iNaturalist first** — decided empirically in Phase 0 by moth coverage + key cleanliness.
- **GADM granularity** — level 1 (state/province) vs level 2 (county). Make it configurable per site/project; default level 1, revisit after Phase 0.
- **Create-vs-skip unmatched taxa** — exposed as `create_missing` (default True). Confirm we want to grow the taxonomy from external sources vs. only intersect with existing taxa.
- **TaxaList scope** — regional lists are project-scoped (not global) so one project's region does not pollute another's picker. Confirmed direction; `get_or_create_for_project(project=...)`.
- **How the pipeline auto-applies masking** — per-`ProjectPipelineConfig` toggle vs. pipeline property. `taxa_list_mode="auto"` at the config level is the minimum; the pipeline-wiring decision aligns with #1289/#999.
- **Name-match fragility** — masking joins on `Taxon.name`; source/classifier spelling mismatches silently drop species. Measured in Phase 0; surfaced per-run via `unmatched_names` + the model-coverage buckets + `not_in_classifier`.

Model & DB awareness questions (§6):
- **Boolean flag vs. through-model, and how to anchor it** — recommendation is the direct `Taxon.covered_by_algorithms` M2M → `Algorithm` + a denormalized `has_model_coverage` boolean, with (a) boolean-only as an acceptable MVP. The remaining choice is whether to store the M2M directly as `Taxon ↔ Algorithm` (recommended; direct read of which model covers a taxon) or normalize it as `Taxon ↔ AlgorithmCategoryMap` to dedup when many algorithms share a map (algorithm answers then derived via the FK) — see §6.2.
- **When to recompute coverage** — on category-map create/update (hook keyed on `labels_hash`) plus an on-demand `refresh_taxon_model_coverage` command. Confirm no other write path (algorithm import, pipeline registration) needs to trigger it, and whether a periodic Celery Beat refresh is warranted as a safety net.
- **DB-presence vs. occurrence-presence** — `has_model_coverage` marks "a model could predict this taxon". Separately, we may want to mark "this taxon has actually been observed in this project" (occurrence-presence) — a different, project-scoped signal. Decide whether the regional-list UI needs both, and keep them distinct (a taxon can be model-covered but never observed, or observed but not model-covered).

Implementation-level questions surfaced here:
- **Sync vs. async for the endpoint/admin action** — regional fetch can exceed request timeouts; likely enqueue a Job (like `sync`), keep `dry_run` synchronous. Decide in Phase 2/4.
- **Cache backend + TTL** for source responses (Redis vs. on-disk; days-scale TTL). Needed once real fetch latency is known (Phase 0).
- **Where `RegionSource` and the masking-resolution helper live** — enum with the model (stable migration path); resolver in `services/` vs. a thin `ml/post_processing/` shim.
- **Reverse-geocode reliability for unattended backfill** — until confirmed, `--all-projects` stays `--dry-run` by default (§8).

## 14. What we still need to verify before building

- Exact GBIF endpoint + params returning a species list for a GADM region, its facet-depth cap, and rate limits — and the iNat equivalent (`species_counts` by `place_id`). Both are on-paper only.
- The GBIF reverse-geocode response shape and which GADM level to take for A3.
- Label-coverage of a generated regional list against a **real** classifier (Quebec/Vermont moths) — the go/no-go for Proposal A standing alone. This is also what validates the §6 default-subset behaviour: if model coverage of a region is very low, the default list will be small and the `include_uncovered` path becomes the common case.
- The cost of refreshing the coverage relationship on large classifiers — how many taxa a real category map resolves to, and whether the per-save hook is cheap enough or should defer to an async task.
- Permissions story for the new fields and the generate action (who may set a region, who may trigger generation) consistent with the project-membership model.
