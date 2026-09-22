# DwC-A Export (PR #1131) — Review & Mapping Spec

> Scope: two distinct parts.
> **Part A** reviews the export implementation (class structure, robustness, operations).
> **Part B** revises the data mapping against project-specific context (CamtrapDP, GBIF camera-trap guide, AMI working-group decisions, InsectAI-Metadata-Standards sheet, Dandjoo conventions).

Related:
- `docs/claude/dwca-format-reference.md` (PR's own reference, authored earlier)
- `docs/claude/export-framework.md` (PR's API/ops reference)
- Google Doc: `1xShA-aRfzSwFQ78MMomUerjU-LD4wOA1VyanukLnIPw`

---

## Part A — Code / Export Approach Review

### A1. Class structure & integration

- `DwCAExporter(BaseExporter)` in `ami/exports/format_types.py:192-290` plugs into the existing export framework (good: inherits filters, progress, artifact upload).
- Term catalogue split into plain Python tuples (`EVENT_FIELDS`, `OCCURRENCE_FIELDS`) in `ami/exports/dwca.py:26-98`. Simple and readable, but:
  - **Mapping logic is colocated with term declarations** via lambdas. This is fine for ~20 fields, but becomes hard to test in isolation. Consider a small `DwCField` dataclass (`term`, `header`, `required`, `extract`, `domain`) to enable: per-field unit tests, per-field null-handling rules, and programmatic generation of `meta.xml`.
  - `generate_meta_xml()` reconstructs the same term URIs it already has in the tuples — the two are not a single source of truth. A field catalogue object would let meta.xml be *derived*, not re-written.
- **Extension model used**: Event Core + Occurrence extension only. No Multimedia / MeasurementOrFact yet. This is the biggest structural decision to revisit in Part B — the working group's Oct 2024 notes and Slide 14 of the Montreal 2024 deck both point to Occurrence Core + Multimedia (Audubon) as the mainstream GBIF pattern. The PR's Event-Core choice is defensible but underjustified.

### A2. Robustness / correctness issues visible in the diff

| Severity | Issue | Location | Status |
|---|---|---|---|
| High | `meta.xml` declares `<coreid index="0"/>` and *also* emits a `<field index="0">` for the same column. Spec-ambiguous. | `dwca.py` meta-gen | Flagged by Copilot, not yet cleanly resolved |
| High | `individualCount` was set to `detections_count` (bounding-box count across frames, not individuals) | `dwca.py` | Fixed → hardcoded `"1"` — but `"1"` is also wrong when a future pipeline counts multiples; needs a model-level source |
| High | PII leak: project owner email written to EML `<surName>` | EML gen | Fixed (a74aee98) |
| Med | Temp files created with `delete=False`, not cleaned on exception | `format_types.py` | Fixed via `try/finally` (ad1b9109) |
| Med | `get_filter_backends()` returned empty list → user filters ignored | `format_types.py` | Fixed (c43d4069) |
| Med | Events derived independently from the filter set → could include events with no published occurrences | `format_types.py` | Fixed by deriving event IDs from filtered occurrences |
| Med | Progress callback fires every 500 rows → small jobs show 0% | export loop | Partially addressed (final update call) |
| Low | `taxonRank.lower()` on possibly `None` | `dwca.py:63` | Fixed |
| Low | `vernacularName` lambda precedence ambiguous | `dwca.py:83` | Fixed |
| Low | EML version mismatch (docs 2.2.0 vs impl 2.1.1); `schemaLocation` relative path | EML | Partially fixed |

### A3. Issues *not* yet raised that should be before merge

1. **No runtime validation pass before zipping.** A malformed archive only fails on the GBIF side. Add a post-write validation step (check: coreid uniqueness, non-null required terms, UTF-8, line-count parity between TSV and `<files>` declarations).
2. **No explicit `license` / `rights` on the Event rows.** GBIF rejects datasets without a machine-readable license. Project model has no license field yet — surface this as a `Project.license` model addition or a per-export argument.
3. **Taxonomic hierarchy via `parents_json` string-matching is fragile.** `_get_rank_from_parents` walks a denormalized JSON blob; if rank strings drift (`"Order"` vs `"order"`), data silently disappears. Prefer an explicit join on `Taxon.rank` through a recursive CTE, or at minimum a normalization pass.
4. **`specificEpithet` by splitting `scientificName` on whitespace is wrong** for subspecies, hybrids, "cf." qualifiers, and authorship strings. Should come from a structured `Taxon` field or be left blank.
5. **`apply_default_filters()` is not invoked in the export queryset.** Project-level score thresholds and taxa include/exclude lists (the standard AMI filter) are bypassed — so low-confidence ML output is exported. Either invoke `apply_default_filters` directly, or document why the export deliberately ignores it.
6. **`identifiedBy` / `dateIdentified` unpopulated.** Flagged as TODO in PR description but is essential for any ML-provenance claim; without it the archive claims a `MachineObservation` by an unknown identifier.
7. **Memory shape of the export loop.** Currently streams rows one occurrence at a time with `.iterator()` (good) but enriching each occurrence walks `parents_json` (a JSON decode per row) and does per-row `determination.common_name_en` (triggers N+1 without `select_related`). Verify select_related/prefetch_related on the queryset.
8. **Concurrency / partial-write failure mode.** If export crashes mid-loop, the ZIP is never assembled but the temp files linger (pre-fix) or are removed (post-fix) — however `DataExport.status` transitions aren't bulletproof. Confirm the Celery task wrapping handles `SoftTimeLimitExceeded` and marks the export as failed.
9. **Archive determinism.** TSV row order = queryset order. For reproducibility (diffable re-exports, GBIF versioning), prefer a stable ORDER BY on `(event.start, occurrence.id)`.
10. **No CI check against GBIF's DwC-A validator.** A single offline invocation of `gbif-dwca-validator` against the fixture archive would catch nearly every class of bug above.

### A4. Testing

Good: 10 tests in `DwCAExporterTests`, use `setUpClass` for shared export.
Gaps:
- No test asserts `meta.xml` parses and validates against the GBIF DwC schema.
- No test for the null-event / null-determination filter (added in `d11976e7` — confirm coverage is explicit, not implicit).
- No test that exported `occurrence.txt` round-trips through GBIF's validator or at least a `dwclib` / `pygbif` parse.
- No test for multi-taxon parent walking (genus-only taxa, subgenus, ranks beyond species).

### A5. Operational concerns

- **Publishing pathway is not wired.** The archive is produced but there's no IPT integration, no DOI minting, no versioning. Document this as out-of-scope or stub the upload target.
- **Re-exports overwrite or version?** Unclear from the diff. GBIF consumes archives by `dataset UUID + version`; producing identical `occurrenceID`s on every re-export is correct only if the publishing target treats new archives as new versions of the same dataset.
- **Sensitive taxa handling.** No `dwc:informationWithheld` / coordinate generalization pass. Endangered species occurrences should be generalized before publication. Currently all lat/lon export at full precision.

---

## Part B — Data Mapping Review

This section supersedes the mapping baked into `ami/exports/dwca.py` and proposes a project-specific spec grounded in: GBIF Camera Trap guide, CamtrapDP, the AMI Metadata Standards WG (July & Oct 2024), InsectAI-Metadata-Standards sheet, Dandjoo, and Slide 14 of the Montreal 2024 deck.

### B1. Archive shape (the structural decision)

The current PR uses **Event Core + Occurrence extension**. The alternatives on the table:

| Option | Core | Extensions | Rationale |
|---|---|---|---|
| **1. Current PR** | Event | Occurrence | Simple; but no place to attach multimedia or ML provenance without violating star schema |
| **2. GBIF camera-trap canonical** | Occurrence | Multimedia (Audubon Core), MeasurementOrFact | Recommended by GBIF camera-trap guide; loses sampling-event metadata (must embed in each occurrence) |
| **3. CamtrapDP → DwC-A downscale** | Event | Occurrence, Multimedia, MeasurementOrFact | Richest; CamtrapDP has a documented downscale path. Matches AMI WG direction. |
| **4. CamtrapDP native + DwC-A sibling** | — | — | Export both; CamtrapDP for insect-specific richness (annotation + model tables), DwC-A for GBIF ingestion |

**Recommendation: Option 3 (Event Core + Occurrence + Multimedia + MeasurementOrFact)** as the near-term target. Option 4 (native CamtrapDP) is the longer-term target once `Deployment`/`Event` models carry the required CamtrapDP fields (`captureMethod`, `timestampIssues`, `baitUse`, `attractantType`, etc.).

The WG's Oct 2024 decision point matters: they want to add an **annotation table** and **model metadata table** as CamtrapDP extensions to capture multiple-classifications-per-detection and model provenance. Neither fits the DwC star schema. For the GBIF-facing archive, collapse to a single "preferred" classification per occurrence; for the richer AMI internal export, use CamtrapDP.

### B2. Term-by-term mapping (proposed, revised from `dwca.py`)

Legend: **bold** = required for GBIF acceptance; *italic* = recommended; plain = optional.

#### B2.1 Event Core (`event.txt`) — per AMI `Event`

| DwC term | Source | Change from PR | Notes |
|---|---|---|---|
| **eventID** | `urn:ami:event:{project.slug}:{event.id}` | keep | ✓ |
| **eventDate** | `event.start` / `event.start/event.end` ISO 8601 interval | keep | ✓ |
| eventTime, year, month, day | derived | keep | ✓ |
| **samplingProtocol** | new `Deployment.sampling_protocol` text field | replace hardcoded | Currently `"automated light trap with camera"` — hardcoded string loses deployment-specific info (UV vs actinic, trigger type, etc.) |
| *sampleSizeValue* | `event.captures_count` | keep | ✓ |
| *sampleSizeUnit* | `"images"` | keep | ✓ |
| *samplingEffort* | duration | keep | Consider `"N trap-nights"` for multi-night events |
| *locationID* | deployment slug/URN, not name | change | `Deployment.name` is not a stable ID; use `urn:ami:deployment:{project.slug}:{deployment.id}` |
| **decimalLatitude**, **decimalLongitude** | `deployment.latitude/longitude` | keep | ✓ |
| **coordinateUncertaintyInMeters** | new field on `Deployment`; default 30m | **add** | Required for GBIF; currently missing |
| *geodeticDatum* | `"WGS84"` | keep | ✓ |
| *countryCode* | new, from reverse geocoding of lat/lon, cached | **add** | ISO 3166-1 alpha-2 |
| stateProvince, locality | optional, from reverse geocoding | add | |
| *datasetName* | `event.project.name` | keep | ✓ |
| **license** | `project.license` (new model field) | **add** | Required for GBIF |
| *rightsHolder* | `project.rights_holder` (new) | add | |
| *institutionCode* | `project.institution_code` (new) | add | |
| dc:modified | `event.updated_at` | keep | ✓ |
| eventRemarks | `event.notes` if available | add | |

**AMI-specific add:** `dwc:parentEventID` pointing to a deployment-level event, to preserve the `Deployment → Event` hierarchy. This addresses the WG's requirement that individuals can be tracked across snapshots within a sampling period.

#### B2.2 Occurrence extension (`occurrence.txt`) — per AMI `Occurrence`

| DwC term | Source | Change from PR | Notes |
|---|---|---|---|
| **eventID** | coreid, as currently | keep | ✓ (meta.xml: coreid only, do NOT double-map as a field — this is the bug flagged by Copilot) |
| **occurrenceID** | `urn:ami:occurrence:{project.slug}:{occurrence.id}` | keep | ✓ |
| **basisOfRecord** | `"MachineObservation"` if ML-only; `"HumanObservation"` if a human Identification is the determination | refine | Currently hardcoded `MachineObservation`; should flip when `occurrence.identifications.exists()` |
| *occurrenceStatus* | `"present"` | keep | ✓ |
| **scientificName** | `occurrence.determination.name` | keep | ✓ |
| *verbatimScientificName* | original classifier output (pre-backbone match) | **add** | Dandjoo convention; useful when backbone mapping is lossy |
| *taxonRank* | `occurrence.determination.rank` lowercased | keep | ✓ |
| *kingdom, phylum, class, order, family, genus* | from `parents_json` via recursive lookup | change source | Prefer recursive CTE or `Taxon.parent` walk over JSON string matching |
| specificEpithet | `Taxon.specific_epithet` field (to add) | change source | String-splitting is unreliable |
| *vernacularName* | `determination.common_name_en` | keep | ✓ |
| *taxonID* | `determination.gbif_taxon_key` | keep | ✓ |
| nameAccordingTo | `"GBIF Backbone Taxonomy {date}"` | add | |
| *individualCount* | `occurrence.individual_count` (new field, default 1) | **change** | `"1"` hardcode is wrong once group counting is added; defer to model |
| organismQuantity / organismQuantityType | optional future | skip for now | |
| **identifiedBy** | pipeline name+version for ML; user email-or-username for human | **add** | Currently blank — essential |
| **dateIdentified** | `classification.created_at` (latest) / `identification.created_at` | **add** | Currently blank |
| **identificationVerificationStatus** | `"verified"` if Identifications present, else `"unverified"`; `"rejected"` if all Identifications disagree with ML | keep but refine | PR uses binary; consider three-state per camera-trap guide |
| identificationRemarks | `f"pipeline={...};score={...}"` if MeasurementOrFact not used | add | |
| identificationQualifier | `"cf."` for below-threshold ML-only occurrences (optional) | add | |
| associatedMedia | pipe-separated URLs of the occurrence's detection source images | **add** | Flagged as TODO; see B2.3 for richer Multimedia extension |
| recordedBy | `deployment.recorded_by` or `project.institution_code` | add | |
| dc:modified | `occurrence.updated_at` | keep | ✓ |

#### B2.3 Multimedia extension (`multimedia.txt`) — **NEW**, per source image linked to published occurrences

Uses GBIF simple multimedia (`http://rs.gbif.org/terms/1.0/Multimedia`) rather than full Audubon for simplicity.

| term | source | notes |
|---|---|---|
| coreid | `eventID` (if Event core) | Star-schema limit: multimedia attaches to the core, not to occurrence. Carry `occurrenceID` in `references` field as a workaround. |
| dc:type | `"StillImage"` | |
| dc:format | `"image/jpeg"` (or detected) | |
| *dc:identifier* | full public URL of the SourceImage | |
| *accessURI* | same | |
| *dc:created* | `source_image.timestamp` | |
| *dc:license* | `project.license` | |
| *dc:rightsHolder* | `project.rights_holder` | |
| *dc:creator* | `deployment.name` or operator | |
| *dc:description* | `f"Detection of {taxon.name}"` | |
| references | occurrence detail URL in the AMI UI | workaround for occurrence linkage |

**Filter:** only publish media linked to at least one published occurrence. Exclude blanks and any image flagged `contains_humans` (WG requirement).

#### B2.4 MeasurementOrFact extension (`measurementorfact.txt`) — **NEW**, carries ML confidence

| measurementType | measurementValue | measurementUnit | measurementDeterminedBy |
|---|---|---|---|
| `"classificationScore"` | `classification.score` (0–1) | `"proportion"` | `f"{pipeline.name} v{pipeline.version}"` |
| `"detectionScore"` | `detection.score` | `"proportion"` | detector algorithm name |
| `"boundingBox"` | JSON `[x1,y1,x2,y2]` normalized | `"normalized"` | detector |
| `"classificationRank"` | `"top1"` or `"top2"`... | — | pipeline |

This resolves the WG's open question about how to publish confidence: raw score in a structured, machine-readable place (not buried in free-text remarks). Top-N predictions can be emitted as multiple rows per occurrence.

#### B2.5 EML — package metadata

Current impl mostly works; required changes:
- Upgrade to EML 2.2.0 (align with docs).
- **Never** write user email to `<surName>`; fixed in a74aee98 but regression-test it.
- Compute `<geographicCoverage>` bounding box from actual deployment coordinates (PR has this as TODO).
- Compute `<temporalCoverage>` from actual min/max `event.start`.
- Populate `<keywordSet>` with `["automated insect monitoring", "camera trap", "Lepidoptera", project taxa]`.
- Populate `<methods>` section with sampling protocol + ML pipeline names used.
- Explicit `<intellectualRights>` with the project license.

### B3. What to *not* export (filter rules)

- Occurrences with `determination IS NULL` ✓ (already filtered)
- Occurrences with `event IS NULL` ✓ (already filtered)
- Occurrences with `determination_score < project.default_score_threshold` — **add** (currently missing; this is what `apply_default_filters` enforces elsewhere)
- Occurrences whose taxon is in `project.default_excluded_taxa` — **add**
- SourceImages flagged `contains_humans` — **add**
- SourceImages flagged `is_blank` with no linked occurrences — skip naturally

### B4. AMI-specific mapping decisions (from WG notes)

1. **Absences as zero-count events.** When a full Event (sampling period) produced no valid occurrences, emit the event row with a MeasurementOrFact `"individualsObserved" = 0`. Do not suppress the event. (WG July 2024.)
2. **Model identity.** For now, `identifiedBy = f"{pipeline.name} v{pipeline.version}"` and `measurementDeterminedBy` mirrors. Once the WG's model-metadata registry exists, replace with a resolvable model DOI.
3. **Confidence score interpretation.** Raw 0–1 in MeasurementOrFact (machine-consumable); no coarse tier in the DwC-A export (display-layer concern). The tier belongs in the AMI UI, not in the archive.
4. **Multiple classifications per detection.** Not representable in DwC-A; preserve only the "preferred" determination per occurrence. Export the full multi-classification graph via CamtrapDP + annotation extension (future work).
5. **Attributes (flying / resting / nectaring / torn wing).** If captured on the Classification, expose as MeasurementOrFact rows with `measurementType = "behavior:flying"` etc. Skip in v1 if data isn't populated.
6. **Unprocessed / expected images.** No current DwC term; capture in EML `<methods>` as text. Flag for the WG.

### B5. Out-of-scope for this PR (future work)

- CamtrapDP native export (parallel to DwC-A)
- Annotation table extension (multi-classification provenance)
- Model metadata table + DOI registry integration
- Sensitive-taxa coordinate generalization
- Automated GBIF validator CI step
- IPT / DOI / dataset-versioning integration

---

## Open questions to resolve with reviewers

1. Is Event Core or Occurrence Core the right choice for the GBIF-facing archive? (B1)
2. Do we want `apply_default_filters()` on by default, or an explicit `--include-low-confidence` opt-in for re-processing pipelines? (A3 §5)
3. Which license do projects default to? Is `project.license` a required field at project creation? (A3 §2)
4. Is there appetite to add `Taxon.specific_epithet` and `Taxon.parent_cache` (recursive-CTE-backed) to kill the string-split and JSON-walk? (B2.2)
5. For multi-classification occurrences, what counts as the "preferred" determination in DwC-A? (B4 §4)
