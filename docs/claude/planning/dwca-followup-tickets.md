# DwC-A export follow-up tickets (single issue draft)

**Status:** draft — do NOT post yet. Intended as one GitHub issue filed after #1131 merges, grouping the items explicitly deferred from that PR.

---

## Title

`DwC-A export follow-ups (perf, data quality, scope)`

## Context

PR #1131 shipped the April 2026 DwC-A draft: Event Core + Humboldt eco: terms + Occurrence / Multimedia / MeasurementOrFact extensions, EML 2.2.0, and an offline structural validator gated as a pre-zip check. CodeRabbit review surfaced several items that were deliberately scoped out to keep that PR focused on the archive contract. This issue tracks them as a single bundle so they can be sequenced together.

## Items

### 1. Perf: streaming fan-out for very large projects (>100K occurrences)

**Status:** Partially addressed in PR #1131. `DwCAExporter.export()` now materializes `self.queryset` to a `list[Occurrence]` once (with all prefetches) and fans out to the three writers; a 100K hardcap (`DwCAExporter.DWCA_MAX_OCCURRENCES`) refuses exports larger than that with a clear error. The follow-up is removing the cap.

**Why:** The materialize-once approach scales linearly in memory (~1 GB for 100K occurrences with prefetched detections + source images). For the AMI dataset today this is fine, but a genuinely large project would still OOM a worker.

**Follow-up work:** Implement **stream once, emit side-by-side**: sort occurrences by `event_id`, stream through once, emit rows to all three files from a single pass using the classic grouping-by-sort pattern. Memory-bounded regardless of project size. Benchmark against a synthetic 500K-occurrence project before raising or removing the 100K cap.

**References:** CodeRabbit PR #1131 threads `PRRT_kwDOIlxGbc587spb` (iter_multimedia_rows memory) and `PRRT_kwDOIlxGbc587spj` (3× queryset scan). Partial fix in `ami/exports/format_types.py` on the feat/dwca-export branch.

---

### 2. Per-taxon absence occurrences

**Why:** The current export sets `eco:isAbsenceReported="true"` and `eco:targetTaxonomicScope=<LCA>` on every event row — this declares absence-inference capacity but doesn't emit actual absence occurrences. The Humboldt-canonical pattern is one `dwc:occurrenceStatus="absent"` row per target-taxon that was not detected during a given event, making "we proved this species was not present during the sampling window" machine-consumable for GBIF consumers.

**How to apply:** depends on an enumerable target-taxon list. Design doc calls for sourcing from `TaxaList` (per-Site `Site.primary_taxa_list`, falling back to the project's default "all possible species" list). That model wiring is a prerequisite.

**References:** `docs/claude/planning/2026-04-21-dwca-april-draft-design.md` § "Per-taxon absence occurrences — deferred to a follow-up PR".

---

### 3. TaxaList-driven `targetTaxonomicScope`

**Why:** v1 derives `eco:targetTaxonomicScope` by computing the LCA of `project.default_filters_include_taxa`. That is a pragmatic proxy but can be empty or overly broad. The right source is the `TaxaList` attached to a Site (curated checklist per monitoring station), which is also what unblocks absence occurrences above.

**How to apply:** replace the LCA computation in `ami/exports/dwca/targetscope.py` with a lookup against `Site.primary_taxa_list` (falling back to project default) once the TaxaList wiring lands. Same follow-up as item 2.

---

### 4. CamtrapDP sibling export

**Why:** The GBIF Camera Trap Guide recommends CamtrapDP as the primary format for the camera-trap community (Wildlife Insights, Agouti, EU camera-trap networks). GBIF doesn't ingest CamtrapDP in production today, so DwC-A via Humboldt remains the GBIF path, but CamtrapDP matters for non-GBIF consumers.

**How to apply:** separate PR. Shares code generously with DwC-A (the `DwCAField` dataclass pattern, the offline validator, the row-generator shape) but emits a Frictionless Data Package zip with its own schema. Tracked separately in issue #1262; this follow-up ticket should link there rather than duplicate.

---

### 5. Human-identifier opt-in for `dwc:identifiedBy`

**Why:** PR #1131 removed `user.email` from the identifiedBy fallback chain (GDPR concern — published archives mirrored by GBIF are hard to retract). The chain is now `user.name → user.username → user:{pk}`. If the project wants a real human identifier in published archives (e.g., for attribution in peer-reviewed datasets), that should be an explicit opt-in, not an unconditional email fallback.

**How to apply:** needs a product decision on UX. Options: per-user "publish my name in open data" toggle; project-level "publish identifier users' names" setting; per-identification opt-in at time of verification. Likely smallest-useful is a user-profile boolean that gates whether `user.email` (or a display name) is used when the user has no `user.name` set.

**References:** CodeRabbit PR #1131 thread `PRRT_kwDOIlxGbc587spn`.

---

### 6. BoundingBox coordinate validation

**Why:** PR #1131 documented that `BoundingBox` coordinates are absolute source-image pixels (they're passed directly to `PIL.Image.crop()`). The docstring makes the invariant explicit, but there's no runtime enforcement. A couple of test fixtures hold normalized `[0, 1]` values that only pass because the test only checks structural validity, not image crops.

**How to apply:** add a Pydantic validator on `BoundingBox` enforcing `x2 > x1`, `y2 > y1`, and non-negative coords. Small, low-risk change, ideally paired with cleanup of the normalized test fixtures so they stop shadowing the production contract.

**References:** CodeRabbit PR #1131 thread `PRRT_kwDOIlxGbc587spd`.

---

### 7. Validator warning path + failure visibility in UI

**Why:** `ValidationResult` supports both `errors` (fatal) and `warnings` (non-fatal), but every finding currently goes through `add_error` — there is no warning path wired up yet. When future vocabulary / backbone / EML schema checks land, they'll need to distinguish "this blocks export" from "this is worth flagging." Related: failure messages are currently buried in Celery/Django logs. The exporter now writes `VALIDATION_ERRORS.txt` into the zip and persists the failed zip to storage so users can download it and read the report, but the DataExport model has no `status` or `error_message` field — the UI only knows "file_url populated" vs. "not populated."

**How to apply:**
- Add `DataExport.status` (choices: PENDING / SUCCEEDED / FAILED) and `DataExport.error_message` (TextField). Populate on failure. Show prominently in the exports table.
- Introduce at least one warning-category check in the validator so the `warnings` path is exercised. Candidates: "meta.xml omits a recommended column," "EML schema location unreachable," "project.license is the default placeholder."

**References:** Item 3 of the takeaway review on PR #1131.

---

### 8. Run archive through GBIF DwC-A Validator

**Why:** The offline structural validator catches drift bugs (meta.xml vs. TSV column counts, dangling coreids) but does not check DwC vocabulary compliance, EML 2.2.0 schema conformance, Humboldt extension vocabulary, or taxonomic backbone matching. The archive has never been through <https://tools.gbif.org/dwca-validator/> or GBIF's IPT. The "April 2026 Draft" label is load-bearing until this runs cleanly.

**How to apply:** add a Makefile target (or scripts/validate_dwca_via_gbif.sh) that (1) generates a fixture export, (2) uploads to or pipes through the GBIF validator, (3) asserts 0 schema errors. Blocks removing the "draft" label from the UI selector. Does not block merging PR #1131.

**References:** Item 6 of the takeaway review on PR #1131.

---

## Sequencing suggestion

1. **(8) GBIF validator** — blocks "remove draft label." Do first so we know what else is actually broken before investing in the others.
2. **(6) BoundingBox validation** — smallest, unblocks confidence in downstream detection-related code.
3. **(7) Status + error_message on DataExport** — gives users a real failure signal; small model + serializer change.
4. **(1) Streaming fan-out** — benchmark-driven. Do before raising the 100K hardcap.
5. **(3) TaxaList scope** + **(2) absence occurrences** — coupled. Wait until `TaxaList` / `Site.primary_taxa_list` wiring lands, then land both in one PR.
6. **(5) identifiedBy opt-in** — needs product input before coding. File a short RFC.
7. **(4) CamtrapDP** — tracked separately in #1262; cross-link from here.

## Closing criteria for this tracking issue

Individual items ship in their own PRs and link back here. Close this issue when (1), (2), (3), (5), (6), (7), (8) are either merged or explicitly decided-not-to-do. (4) is tracked separately and doesn't block closure here.
