# Taxa List Export — Design

**Date**: 2026-05-05
**Branch**: `worktree-taxa-list-export`
**Author**: Michael + Claude

## Goal

Add a new export format `taxa_list_csv` to the existing export framework
(`ami/exports/`). One row per unique taxon that has at least one valid
occurrence (after applying project default filters) in the user-selected
`SourceImageCollection`. Output is a tabular CSV.

This is not Darwin Core. It is a project-internal summary file for collaborators
who want a quick "what showed up in this capture set" report.

## Scope decisions

| Question | Decision | Why |
|---|---|---|
| Which taxa? | Distinct `determination` taxa from valid occurrences in the collection, **with project default filters applied** (score threshold + include/exclude taxa lists, via `Occurrence.objects.apply_default_filters`) | Matches what users see in the Taxa list view. Screens out unreviewed low-score ML output before it leaves the system. |
| Hierarchical roll-ups (a row for the species *and* its genus, family, etc.) | **No.** One row per directly-determined taxon. | Simpler. Most projects don't classify at every rank, but when they do (e.g. genus-level when species fails), each taxon already gets its own row because it appears as someone's `determination`. |
| Column name for occurrence count | `direct_occurrences_count` | Makes it explicit that this counts occurrences whose `determination` *is* this taxon, not descendants. Leaves room for a future `recursive_occurrences_count` column if requested. |
| Output formats | CSV only (v1) | Matches existing `occurrences_simple_csv`. JSON variant deferrable. |
| Time-of-night handling | Shift to "minutes from noon" before aggregating to handle midnight wraparound. Output as `HH:MM:SS`. Use first-appearance time of each occurrence (i.e. earliest detection timestamp). | Naive midnight-anchored avg of 22:00 and 02:00 is 12:00 (wrong). Noon-anchored avg is 00:00 (correct midpoint). |
| Filter backend | New `TaxaListCollectionFilter` that consumes `collection_id` and constrains to occurrences in that collection. (Cannot reuse `OccurrenceCollectionFilter` because it wraps the queryset in a subquery on `Occurrence`, not on the per-taxon aggregate.) | Filter backend pattern is the right place to apply the collection scope; the rest of the framework (`apply_filters`) already invokes it. |

## Output columns

Group A — Taxon identity:
- `id`, `name`, `display_name`, `rank`, `common_name_en`

Group B — Taxonomy hierarchy from `parents_json` (one column per Linnaean rank in `DEFAULT_RANKS`):
- `kingdom`, `phylum`, `class`, `order`, `family`, `subfamily`, `tribe`, `genus`, `species`
  (extracted from `parents_json`; populated only if a parent at that rank exists; the row's own taxon fills in its rank's column)

Group C — Occurrence aggregations (over filtered occurrences in collection):
- `direct_occurrences_count` (int)
- `min_score`, `max_score`, `avg_score` (float, 4 decimal places)
- `first_occurrence_date`, `last_occurrence_date`, `avg_occurrence_date` (`YYYY-MM-DD`)
- `min_time_of_night`, `max_time_of_night`, `avg_time_of_night` (`HH:MM:SS`, noon-anchored aggregation)

Group D — External IDs and links (blank when the field is null):
- `gbif_taxon_key`, `gbif_url`
- `inat_taxon_id`, `inat_url`
- `bold_taxon_bin`, `bold_url`
- `fieldguide_id`, `fieldguide_url`
- `cover_image_url`

Link templates:
- GBIF: `https://www.gbif.org/species/{key}`
- iNaturalist: `https://www.inaturalist.org/taxa/{id}`
- BOLD: `https://www.boldsystems.org/index.php/Public_BarcodeIndexNumber_RecordView?searchtype=records&recordID={bin}`
- Fieldguide: `https://fieldguide.app/taxa/{id}`

## Architecture

```
ami/exports/
├── base.py              # add `filename_label` class attr (generic, copied from PR #1131)
├── format_types.py      # add TaxaListCSVExporter
├── taxa_list.py         # NEW — column getters, time-of-night helpers, aggregator
├── registry.py          # register "taxa_list_csv"
├── models.py            # generate_filename uses filename_label if set
└── tests.py             # add TaxaListExportTest

ami/main/api/views.py    # NEW filter backend: TaxaListExportCollectionFilter (or
                         # reuse TaxonCollectionFilter if signature aligns)

ui/src/data-services/models/export.ts   # add 'taxa_list_csv' to SERVER_EXPORT_TYPES
                                        # add label "Taxa list (CSV)"
```

## Data flow

1. `DataExport` row created with `format='taxa_list_csv'` and `filters={'collection_id': N}`.
2. Job kicked off → `DataExport.run_export()` → `TaxaListCSVExporter.__init__` calls
   `BaseExporter.apply_filters` to apply the collection filter to the **occurrence**
   queryset (so we can count/aggregate without touching N taxa rows).
3. `total_records` becomes the count of distinct taxa with ≥1 filtered occurrence
   (computed via `qs.values('determination_id').distinct().count()`), so progress
   reflects the real output size.
4. `export()` does:
   - **One streaming pass** over the filtered occurrence queryset, ordered by
     `determination_id`, yielding `.values('determination_id', 'determination_score',
     'first_appearance_timestamp', 'last_appearance_timestamp')` (use `with_timestamps()`).
   - Per-taxon accumulator dict `{ det_id: TaxonAccumulator }` — running min/max/sum
     for score, first_appearance_dt, last_appearance_dt, and noon-anchored
     time-of-night seconds.
   - After streaming, `Taxon.objects.filter(id__in=accum.keys())` fetches taxon
     rows for the column-A/B/D fields.
   - For each taxon, write one CSV row using the accumulator + taxon fields.
   - `update_job_progress` ticks per row.

## Aggregation details

### Score
Running `min`, `max`, `sum`, `count` (skip None). `avg = sum / count` if `count > 0`.

### Date (date-of-occurrence)
Use `first_appearance_timestamp.date()`. Running min, max, and "average epoch seconds"
(via Welford's incremental mean to avoid overflow). Convert avg back to `date`.
For exports the average-date column is informational; not a quantity anyone
math-aggregates further.

### Time of night
For each occurrence, take `first_appearance_timestamp.time()`. Convert to seconds
since midnight. Apply noon shift: `shifted = (secs - 43200 + 86400) % 86400`.
Aggregate min/max/avg in shifted space. Convert back: `secs = (shifted + 43200) % 86400`.
Format as `HH:MM:SS`.

This handles the typical AMI monitoring window (dusk through dawn) without the
naive "average of 22:00 and 02:00 = 12:00 noon" failure.

## Filter backend

`OccurrenceCollectionFilter` is the right shape (`collection_id` → filter on
`detections__source_image__collections`). Override `get_filter_backends()` on
`TaxaListCSVExporter` to return `[OccurrenceCollectionFilter]`. The filtered
queryset stays an `Occurrence` queryset; we group/aggregate from there.

## Generic optimization carried over from PR #1131

Add `filename_label` class attribute to `BaseExporter` (defaults to `""`). When
non-empty, `DataExport.generate_filename` inserts it as a slug token between the
project slug and the export pk:

`project_slug-{label}_export-{pk}.{ext}`

For `TaxaListCSVExporter`, set `filename_label = "taxa_list"` so the file lands
as `vermont-atlas_taxa_list_export-42.csv` instead of `vermont-atlas_export-42.csv`,
making it distinguishable from occurrence exports in a user's downloads folder.

The two existing exporters keep `filename_label = ""` and produce the same
filenames they do today (no migration / regression).

## Testing

Add `TaxaListExportTest` in `ami/exports/tests.py`:

1. Set up project, deployment, two captures-per-night events spanning midnight.
2. Create occurrences across 3 distinct taxa (different ranks, different
   external-ID populations).
3. Run export; read CSV.
4. Assertions:
   - Row count = distinct determinations (after default filters).
   - `direct_occurrences_count` per row matches manual count.
   - Score min/max/avg are correct.
   - `first_occurrence_date` ≤ `last_occurrence_date`.
   - Time-of-night roundtrip: an occurrence at 22:00 and one at 02:00 next-day
     yield avg ≈ 00:00 (within ±1 minute).
   - `gbif_url` populated when `gbif_taxon_key` is set; blank otherwise.
   - Hierarchy columns populated from `parents_json`.

## Future hook: taxonomic scope / absence rows

A project will eventually declare a "taxonomic scope" — the set of taxa
expected to be observable. Today this is implicit in
`Project.default_filters_include_taxa` (recursively expanded). Per-Site
`TaxaList` may follow.

When the scope is declared, the export should emit a row per scope-taxon that
*was not* observed in the collection, with `direct_occurrences_count = 0`. This
turns the file into a presence/absence checklist rather than a "what we saw"
list — important for ecological interpretation (a taxon is meaningfully
*absent* only against an explicit expected list).

The exporter has a `_get_expected_taxa()` hook returning an empty queryset by
default. When a project gets a populated scope (any of: a non-empty
`default_filters_include_taxa`, a per-project default `TaxaList`, a per-Site
`TaxaList`), this method will be updated to return that taxa set. The writer
loop emits a zero-count row for each expected taxon not in the observed
accumulator.

For v1 the hook is wired but inert (returns nothing); the column shape stays
identical so the format is stable when absence rows turn on.

## DwC Taxon Core compatibility (future `taxa_list_dwca` format)

The DwC-A export in PR #1131 explicitly defers a species-checklist
(`taxon.txt`). The columns this format already produces cover the DwC
Taxon Core terms needed for that follow-up:

| DwC term | Source in this export |
|---|---|
| `taxonID` | `id` (or scoped URN) |
| `scientificName` | `name` |
| `taxonRank` | `rank` |
| `kingdom`, `phylum`, `class`, `order`, `family`, `genus` | hierarchy columns from `parents_json` |
| `specificEpithet` | derivable from `name` when `rank=SPECIES` |
| `vernacularName` | `common_name_en` |
| `scientificNameAuthorship` | `Taxon.author` |
| `nameAccordingToID` | `gbif_url` |
| `references` | `inat_url` / `fieldguide_url` / `bold_url` (pipe-joined) |

Scientific-name authorship + author date are not in v1 columns but are
trivially addable. Implication: a sibling `taxa_list_dwca` format reusing the
same accumulator and Taxon fetch can ship as a single Taxon-Core DwC archive
later. No schema changes needed; just an alternate writer that emits TSV +
`meta.xml` + `eml.xml` in a zip.

For v1 we do NOT ship the DwC variant. The column choices in this CSV are
intentionally a superset of the data needed for it, so the work isn't
re-done.

## Out of scope (follow-up)

- JSON variant (`taxa_list_json`) — straightforward once CSV is in.
- DwC Taxon-Core archive variant (`taxa_list_dwca`) — see above.
- Zero-count absence rows — see "Future hook" above.
- Recursive (`recursive_occurrences_count`) — needs `parents_json__contains`
  count subquery per row; defer until a user asks.
- Per-event time-of-night (some projects might want "average time within event",
  not absolute clock time).
- Tag column / TaxaList membership column.
- `scientificNameAuthorship`, `authorship_date` columns (for DwC variant).

## Implementation order

1. Add `filename_label` to `BaseExporter` + wire through `DataExport.generate_filename`.
2. Implement `ami/exports/taxa_list.py` (accumulator, helpers, CSV writer).
3. Implement `TaxaListCSVExporter` in `format_types.py`.
4. Register `taxa_list_csv` in `registry.py`.
5. Update UI `export.ts` (type + label).
6. Tests.
7. Run full export test suite.

## Risks

- **Memory**: per-taxon accumulators are bounded by the number of distinct taxa
  in the collection. For typical projects (≤ a few thousand taxa), this is well
  under 1 MB. Documented; not actively guarded.
- **Time-of-night assumption**: noon shift is correct for nocturnal AMI traps
  (the only documented use case). For diurnal observations the noon-anchored
  aggregation could be misleading. Not currently a concern; revisit if a daytime
  project shows up.
- **Cross-product on collection filter**: filtering `Occurrence` by
  `detections__source_image__collections` introduces duplicate occurrence rows
  in the join. The `.values('determination_id', ..., 'id')` with `Count('id',
  distinct=True)` pattern handles this. Tests verify counts.
