# Phase 0 findings — regional taxa-list coverage spike (#1364)

**Date:** 2026-07-02
**Verdict:** GO for Proposal A. The candidate GBIF and iNaturalist endpoints work with the parameters the plan assumed, the A3 reverse-geocode path resolves cleanly, and a region-derived list covers a useful majority of a real classifier's labels.
**Script:** `docs/claude/analysis/phase0_regional_coverage_spike.py` (run inside the django container; reads DB + live APIs, writes nothing).

## Setup

- Region: Vermont (chosen to match the Quebec & Vermont classifier).
- Taxon scope: Lepidoptera (GBIF taxonKey 797, iNat taxon_id 47157).
- Classifier under test: local `Algorithm` pk 10, "Quebec & Vermont Species Classifier - Apr 2024", **2497 labels**.
- Name match: exact string on the scientific name (same join class masking uses — `Taxon.name` == label).

## Results (measured, this run)

| Metric | Value |
|---|---|
| Q&V classifier labels | 2497 |
| GBIF VT Lepidoptera species | 2164 |
| iNat VT Lepidoptera species | 1922 |
| Region union (GBIF ∪ iNat) | 2299 |
| Q&V ∩ GBIF | 1743 (69.8% of labels) |
| Q&V ∩ iNat | 1527 (61.2% of labels) |
| **Q&V ∩ union** (default masking-list size) | **1749 (70.0% of labels)** |
| Region species not in Q&V (no-coverage bucket) | 550 (23.9% of the union) |

Reverse-geocode check (A3): point `(44.26, -72.58)` → GADM level-1 gid `USA.46_1` ("Vermont"). The `/geocode/reverse` response carries GADM ids at every level, so deriving a region code from a deployment's stored `latitude`/`longitude` is straightforward — the `--all-projects` backfill path is viable.

## Interpretation

- **A region-derived default list is worth building.** For Vermont it keeps 1749 of 2497 classes and masks ~748 (30%) that neither GBIF nor iNat records in the state — a meaningful, defensible reduction, which is exactly what class masking is for.
- **GBIF is the primary source; iNat is secondary.** GBIF alone reaches 69.8%; adding iNat lifts the *intersection* by only 6 species (to 70.0%). iNat's larger contribution is to the regional *union* (the uncovered bucket), not to classifier coverage. This supports starting Phase 1 with a **GBIF-only** source client and adding iNat later — the wide-union merge still holds, it just starts with one source.
- **The `include_uncovered` opt-in is a real, non-trivial set** (550 species for Vermont). The default-subset-to-model-known behaviour matters: without it, a naive regional list would add 550 taxa no model can predict.

## Caveats / what still needs verifying (carried into Phase 1)

- **Name-join fragility is the top risk.** 748 Q&V labels (30%) are absent from the region union. Some are genuine regional absences; some are likely name-format or synonym mismatches (authorship, subspecies, GBIF/iNat vs. our backbone naming). Before trusting the default list, audit a sample of those 748 to estimate the true-absence vs. mismatch split, and decide whether to widen matching (e.g. `Taxon.search_names`, synonym resolution) — this is the single measurement that most affects list quality.
- **GBIF name resolution is slow** (2164 speciesKey→name lookups took ~92s at 16 threads). Production must cache resolved keys and/or resolve lazily; not a blocker, but the service needs a cache layer.
- **Granularity was GADM level 1 (state).** Level 2 (county) would tighten the list but risk under-including; the region-code field should carry the level, and the right default is an open question.
- **Single region / single classifier tested.** Vermont + Q&V is the friendliest case (the classifier was built for this region). Coverage for a mismatched region (e.g. a tropical site against Q&V) will be far lower — which is the correct behaviour, but worth confirming the numbers degrade sensibly before enabling auto-masking broadly.

## Recommendation for Phase 1

Proceed. Build the core service with a **GBIF-first** source client (iNat behind the same protocol, added second), the wide-union merge, the model-coverage relationship, and the default-subset behaviour — all behind unit tests with a stubbed source (no network in CI). Fold a name-mismatch audit of the uncovered Q&V labels into the Phase 1 work, since it gates how much to invest in fuzzy matching.
