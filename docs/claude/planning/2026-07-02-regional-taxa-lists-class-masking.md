# Let users build a project taxa list from a region, so class masking works out of the box

**Labels:** enhancement, needs design, backend, ml
**Related:** #999 (class masking), #1289 (post-processing framework), #1094 (configurable taxa lists), #939 (import taxa from external lists), #1020 (closed — GBIF taxon select in the UI), #1293 (taxa list CSV export)

## Summary

Class masking (#999) lets an operator keep only the classifier predictions that fall inside a chosen taxa list, which cuts a global classifier down to the species that actually occur at a site. The feature is nearly ready, and the taxa list editor is merged (#1094). The missing piece is the taxa list itself: today someone has to hand-curate one taxon at a time, which is too tedious to expect from project owners, and nothing connects a list to the place a project monitors.

This ticket proposes a way for a user to generate a regional species list automatically from an external biodiversity database (GBIF and/or iNaturalist) by giving a region code, so that curating a project's masking list becomes a single action instead of hundreds. It also proposes where region codes and taxa lists should live on the data model (on the `Site`, with a fall-back on the `Project`), and how the first class-masking pipeline can pick the right list automatically from the occurrence's site rather than making the operator choose one every time.

The core capability — "given a region, produce a taxa list" — is written once as a service function and surfaced through a management command, a Django admin action, an API endpoint, and the main UI, so the same logic can also backfill regional lists for every project already in Antenna.

We should ship the simplest useful version first. My recommendation is Proposal A (generate from a region code) over Proposal B (spreadsheet import with a matching UI); B is more flexible but much more work, and A covers the common case.

---

## Background — current state of the code

Grounded in the current tree so the proposals below reference real names.

**Models**
- There is a `Site` model (verbose name "Research Site", `ami/main/models.py:654`) that groups deployments. It has `name`, `description`, `project` only — **no coordinates, region, or country**. Its geographic extent is derived on the fly from its deployments via `boundary_rect()` (`models.py:670`).
- Coordinates live on `Deployment` (`models.py:763`): `latitude` (`:770`) and `longitude` (`:771`). Deployment has **no `country` or `region` field** either.
- `Occurrence` → site chain: `Occurrence.deployment` (`models.py:3598`) → `Deployment.research_site` (`models.py:803`) → `Site`. `Occurrence` also carries a direct `project` FK (`models.py:3599`).
- `TaxaList` (`models.py:4646`): M2M `taxa` → `Taxon` (`:4652`) and M2M `projects` → `Project` (`:4653`); a list with `projects=None` is a global list. Manager helper `TaxaList.objects.get_or_create_for_project(name, project=None)` (`models.py:4598`).
- `Project` (`models.py:289`): **no default-taxa-list field, no region/country, no geo bounds.** It does have include/exclude *filter* taxa M2Ms on `ProjectSettingsMixin` (`ami/main/models_future/projects.py:42,52`), but those are for the occurrence default-filter system, not a linked `TaxaList`.
- `Taxon` (`models.py:4342`): `name` is globally unique (`:4346`); external keys already exist — `gbif_taxon_key` (`:4364`), `bold_taxon_bin` (`:4365`), `inat_taxon_id` (`:4366`); hierarchy via `parent` (`:4349`) and denormalized `parents_json` (`:4356`).

**Class masking (branch `feat/postprocessing-class-masking`, PR #999; reworked onto the framework in `rework/999-class-masking-on-framework`)**
- `ClassMaskingTask` (`ami/ml/post_processing/class_masking.py:228`), config `ClassMaskingConfig` (`:17`) requires an explicit `taxa_list_id` (`:25`).
- The list is chosen by an operator from an admin dropdown over **all** taxa lists (`ami/ml/post_processing/admin/class_masking_form.py:25`), loaded by PK at run time (`class_masking.py:306`).
- Matching taxa-list membership to classifier categories is effectively **`Taxon.name == classifier label`**, resolved through `AlgorithmCategoryMap.with_taxa()` (`ami/ml/models/algorithm.py:105`, keyed by `taxon.name` at `:135`). `search_names__overlap` widens the DB query but the returned map is name-keyed.
- **Nothing currently selects a list by region, site, or project.** The operator picks a list by hand, and nothing constrains it to the classifier's region or to the project of the rows being processed.

**Post-processing framework (merged, #1289)**
- `make_post_processing_action(...)` (`ami/ml/post_processing/admin/actions.py:177`) builds the admin action; a `build_jobs` hook (`actions.py:87,184`) is the escape hatch for row→Job fan-out. Task params are configured via an admin form only — there is no API surface for triggering post-processing yet.

**Taxa import / external APIs**
- `import_taxa` command (`ami/main/management/commands/import_taxa.py`) ingests a CSV/JSON file (local path or URL), builds the rank hierarchy under an `Arthropoda` root, and creates a **global** list via `get_or_create_for_project(project=None)` (`:240`). It matches taxa **by name only** (`:321`) and has no `--project` argument yet (`@TODO` at `:169`).
- **No live GBIF / iNaturalist / GADM integration exists** anywhere in `ami/`. The `gbif_taxon_key` / `inat_taxon_id` fields are populated from files, never fetched. (PR #1020, closed, did prototype a GBIF taxon-select React component that called the GBIF API from the browser — a useful reference for the UI side.)
- HTTP with retries: `ami/utils/requests.py::create_session()` (`:14`) is the repo convention for outbound API calls.
- All-projects backfill template: `assign_roles.py` loops `Project.objects.all()` (`:79`) — the shape to mirror.

---

## The reusable core (independent of which proposal we pick)

The one thing every proposal needs is a single function:

> **`generate_regional_taxa_list(region, project=None, classifier=None, name=None, dry_run=False) -> Result`**
> Given a region code, fetch the species that occur there from an external source, map them onto Antenna `Taxon` rows, optionally intersect with a classifier's label set, and create (or preview) a `TaxaList` scoped to the project. Returns a summary: matched / unmatched-from-source / not-in-classifier / created counts, plus the unmatched names so a human can review.

Suggested home: `ami/main/services/regional_taxa.py` (new services module — see the "processing logic extraction" note in `CLAUDE.md`).

This function is the single source of truth surfaced five ways, exactly as required:

| Surface | How |
|---|---|
| Management command | `python manage.py generate_regional_taxa_list --project <id> --region <code> [--classifier <id>] [--all-projects] [--dry-run]` — also the backfill tool |
| Unit test | Calls the function directly with a stubbed source client; asserts match counts and idempotency |
| Django admin action | Action on `Project` and/or `Site` changelist → confirmation form (region source + code, optional classifier) → runs the function |
| API endpoint | `POST /api/v2/projects/{id}/taxa-lists/regional/` (and/or a `Site` variant) → returns the preview/result |
| Main UI | "Create taxa list for region" button in Project settings and in the Site editor → calls the API endpoint |

Idempotency matters here: re-running for the same region should update the existing list, not create duplicates (mirror `get_or_create_for_project`). External calls go through `create_session()` for retry/backoff, and results should be cached — GBIF/iNat regional queries are slow and rate-limited.

---

## Proposed data model changes

Minimal columns; polygons and richer geometry come later.

- **`Site`**: add `region_source` (choices: `gbif_gadm`, `inat_place`), `region_code` (char — a GADM GID like `USA.11_1`, or an iNat `place_id`), and `taxa_list` (nullable FK → `TaxaList`). This is where the user's "each site has a region code and a taxa list" lands.
- **`Project`**: add `region_source` + `region_code` and `default_taxa_list` (nullable FK → `TaxaList`) as the fall-back when a site has none.

Note that `TaxaList↔Project` and `TaxaList↔Taxon` are M2M today; the new `taxa_list` / `default_taxa_list` are single FKs layered on top (a project can still be associated with many lists, but has one designated default). Each new field needs a migration in the same PR.

### Resolution order when masking runs

For "the first pipeline that uses class masking applies it automatically", the class-masking task grows an `auto` mode (resolve the list per occurrence) in addition to today's explicit `taxa_list_id`:

```
occurrence.deployment.research_site.taxa_list
  ↳ else research_site.region_code   → generate/lookup regional list
  ↳ else project.default_taxa_list
  ↳ else project.region_code         → generate/lookup regional list
  ↳ else no masking (log and skip)
```

This keeps class masking a no-op until a site or project has a region/list configured, so it is safe to enable by default on a pipeline.

---

## Proposals (simplest first)

### Proposal A — Generate a regional list from a region code *(recommended first)*

User provides a region code (or we derive it, see A3); we fetch the regional species list, intersect it with the classifier's labels, and save a `TaxaList`. One button, no per-taxon work.

Sub-options for the **source API** (can support more than one; start with whichever is easiest to get good moth coverage from):

- **A1 — GBIF occurrence facets by GADM region.** Query GBIF's occurrence search faceted by `speciesKey`, filtered by `gadmGid` (GADM administrative region, level 0/1/2) or `country`, scoped to the relevant taxon (e.g. Lepidoptera key), `hasCoordinate=true`. GADM gives clean nested region codes and pairs naturally with "add polygons later". Species come back with GBIF keys, so mapping to `Taxon.gbif_taxon_key` is exact; fall back to name match.
- **A2 — iNaturalist species counts by place.** `GET /v1/observations/species_counts?place_id=<id>&taxon_id=<Lepidoptera>&quality_grade=research` returns a ranked species list for a place. iNat `place_id`s are easy to look up and map to `Taxon.inat_taxon_id`. Good community coverage; place boundaries are iNat-specific rather than GADM.
- **A3 — Derive the region code from existing coordinates.** Projects already have deployment `latitude`/`longitude`. Reverse-geocode a representative point to a GADM GID (GBIF exposes a reverse-geocode endpoint) or an iNat place, so we can generate lists for **all existing projects** with no manual region entry — this is what makes the "backfill every known project" line item feasible.

**Matching / review.** Because our masking join is `Taxon.name == label`, the value of a regional list is its intersection with the classifier's category map. The function should report, per run: how many source species matched an existing `Taxon`, how many are new (create them via the `import_taxa` hierarchy builder), and how many of the matched taxa are actually in the classifier's labels (only those affect masking). Surface the not-in-classifier count so users understand why a large regional list still only masks to N species.

**Effort:** medium. New service + one source client + model fields + admin action + one API endpoint + a thin UI button. Reuses `create_session`, `import_taxa.create_taxon`, `get_or_create_for_project`.

### Proposal B — Spreadsheet import with a matching interface

User uploads a spreadsheet of species; we match each row against the global classifier's class list and show an intermediate review screen (matched / fuzzy / unmatched, with manual override) before saving the `TaxaList`.

- More flexible than A (handles curated/authoritative lists, non-GBIF sources, local common names).
- Much more work: file parsing, fuzzy matching UI, per-row conflict resolution, persistence of decisions. This is essentially a new interactive workflow.
- Partially foreshadowed by existing pieces: `import_taxa` already parses CSV/JSON and matches by name; #1293 already emits a taxa-list CSV (the reverse direction). A matching-review UI is the new part.

**Recommendation:** defer. A regional generator (A) removes most of the tedium for the common case; B is the power-user path once A is in and we see what still needs manual curation.

### Proposal C — Polygons / geometry *(explicitly future)*

Store real geometry on `Site` (GeoDjango — there is already a commented-out TODO at `models.py:666`) and compute regional lists from a drawn boundary rather than an administrative code. Out of scope here; the `region_source`/`region_code` fields in A are designed so a `polygon` source can be added later without reworking the resolution order.

---

## What we'd ship first (proposed slice)

1. Service function `generate_regional_taxa_list(...)` + one source client (A1 **or** A2 — pick based on moth coverage) behind `create_session`.
2. Model fields on `Site` and `Project` + migration.
3. Management command wrapping the service, including `--all-projects` backfill using A3 reverse-geocoding.
4. Admin action on `Project`/`Site` (fastest path to internal use; matches the #1289 admin-first pattern).
5. Wire the class-masking `auto` resolution order so a pipeline can apply masking without an operator choosing a list each run.

API endpoint + main-UI button follow once the service and its output are validated internally.

---

## Open questions / decisions to make

- **GBIF vs iNaturalist as the first source.** Which gives better regional moth coverage and cleaner keys for our classifiers? (Leaning GBIF+GADM for A1 because keys and nested regions are cleaner, but iNat place counts may match community reality better.)
- **Region granularity.** GADM level 1 (state/province) vs level 2 (county/district) — too coarse over-includes species, too fine under-includes. Configurable per site?
- **Create-vs-skip unmatched taxa.** When a source species has no `Taxon` row, do we create it (grows the taxonomy from an external source) or only keep intersections with existing taxa? Creating is more complete but imports taxa we may never classify.
- **`TaxaList` scope.** Regional lists are project-specific by nature; confirm they should be project-scoped lists (not global) so one project's region doesn't pollite another's list picker.
- **How the pipeline "auto-applies" masking.** Is it a per-`ProjectPipelineConfig` toggle, or a property of the pipeline itself? Needs to align with the #1289 framework and #999's config.
- **Name-match fragility.** Since masking joins on `Taxon.name`, mismatches between GBIF/iNat names and our classifier labels silently drop species. We should measure the miss rate on a real classifier before trusting auto-masking.

## What we still need to verify (before building)

- Confirm the exact GBIF endpoint + params that return a species list for a GADM region with acceptable rate limits, and the iNat equivalent — on paper both exist, but neither has been exercised from this codebase.
- Measure, for one real classifier (e.g. the Quebec/Vermont moths model), how many of its labels a generated regional list actually covers — this decides whether A is useful on its own or needs B's manual curation.
- Confirm reverse-geocoding deployment coordinates to a region code is reliable enough to backfill existing projects unattended, or whether it needs human confirmation per project.
- Decide the migration/permissions story for the new `Site`/`Project` fields (who can set a region, who can trigger generation) consistent with the project-membership model.
