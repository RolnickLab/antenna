# DwC-A April 2026 Draft — Design (in progress)

**Status:** Brainstorming in progress. Converged on Event Core, verifying against GBIF guide before final commit.
**PR:** #1131 (`feat/dwca-export`)
**Owner:** Michael / Claude session
**Date:** 2026-04-21

---

## Decision trail so far

### Core choice: Event Core (retained from current PR)

Initially proposed flipping to Occurrence Core per user direction, then surfaced the
star-schema consequence: in Occurrence-Core, every extension row must have `coreid =
occurrenceID`, which forces `event.txt` to duplicate event rows per-occurrence (50
near-identical rows for an event with 50 occurrences). Reconsidered and landed on
**Event Core** because:

1. **Absence inference** — automated camera-trap sampling (photo every 10s all night)
   enables *strong* absence inference: we can prove species X was not present during
   this sampling window. This is the scientific breakthrough of automated monitoring.
   Event Core carries structured sampling effort natively (duration, protocol, light
   type, sample size); Occurrence Core loses it except as EML free-text. Shipping a
   DwC-A that erases our strongest scientific contribution is wrong.
2. **AMI's data shape** — many occurrences per event (one night = 100s of moths); Event
   Core eats the smaller redundancy tax (one `occurrenceID` column on MoF/multimedia
   rows) versus Occurrence Core (full row duplication in event.txt or wholesale
   denormalization onto every occurrence row).
3. **CamtrapDP alignment** — CamtrapDP's `events` table maps ~1:1 onto our `event.txt`.
   Event Core today makes the CamtrapDP follow-up PR easier, not harder.

### Archive shape

```
project_export.zip
├── meta.xml
├── eml.xml                  ← EML 2.2.0
├── event.txt                ← Event Core — one row per AMI Event
├── occurrence.txt           ← Occurrence extension — coreid=eventID
├── multimedia.txt           ← GBIF simple Multimedia extension — coreid=eventID
│                                (holds both capture images and detection crops;
│                                 detection-crop rows carry occurrenceID column
│                                 to link back to their occurrence)
└── measurementorfact.txt    ← MoF extension — coreid=eventID
                                 (carries classificationScore, detectionScore,
                                  boundingBox; per-occurrence rows carry
                                  occurrenceID column; per-event rows don't)
```

The `occurrenceID` column is a valid DwC term that extensions are legally allowed to
carry. Using it in multimedia and MoF rows is not a hack — it's how Event-Core archives
point extension rows back to specific occurrences.

### occurrence.txt (extension) — columns

Keep all current columns. Add:

- `associatedMedia` — pipe-separated public URLs of source captures that produced this
  occurrence's detections (distinct, ordered by detection timestamp). Redundant with
  multimedia.txt but useful for quick consumers.

### event.txt (core) — columns

Inherits current event columns. Already present: `eventID, eventDate, eventTime, year,
month, day, samplingProtocol, sampleSizeValue, sampleSizeUnit, samplingEffort,
locationID, decimalLatitude, decimalLongitude, geodeticDatum, datasetName, license,
rightsHolder, modified`. Add:

- `parentEventID` — blank for now (would link deployment-level parent once that model
  exists). Documented as follow-up in PR body.
- Placeholder columns for Device fields (`deviceType`, `attractantType`,
  `lightWavelength`) — **deferred to follow-up PR** with the Device model migration.

### multimedia.txt — columns

Columns: `coreid (=eventID), occurrenceID, type, format, identifier, references, created,
license, rightsHolder, creator, description`.

Row shape:
- **Capture image rows:** one per SourceImage in an event linked to ≥1 published occurrence.
  `occurrenceID` blank. `identifier` = capture URL.
- **Detection crop rows:** one per Detection whose occurrence is in the filter set.
  `occurrenceID` populated with the detection's occurrenceID URN. `identifier` = crop URL;
  `references` = source capture URL.

Filter rules: exclude `is_blank` and `contains_humans` SourceImages (WG requirement).

### measurementorfact.txt — columns

Columns: `coreid (=eventID), occurrenceID, measurementID, measurementType,
measurementValue, measurementUnit, measurementDeterminedBy, measurementRemarks`.

Row types:
- **Per-occurrence:** `classificationScore` (value, unit=proportion, determinedBy=pipeline
  name+version). `occurrenceID` populated.
- **Per-detection:** `detectionScore` (proportion, detector algorithm), `boundingBox`
  (JSON `[x1,y1,x2,y2]`, normalized or pixels). `occurrenceID` populated.
- **Per-event (future hook):** no rows emitted yet; slot for future lux, temperature,
  moon phase.

### EML 2.2.0 upgrade

- Bump namespace + schemaLocation
- Compute `geographicCoverage` bbox from deployment lat/lon min/max across the filter set
- Compute `temporalCoverage` from min/max `event.start`
- `methods` section: sampling protocol text + list of pipelines used (name+version) +
  `qualityControl` para noting default filters applied
- Keep current license + rights-holder behavior

### Runtime pre-zip validation

Reuse `ami/exports/dwca_validator.py` on temp TSVs before packaging. Extend validator to
cover: (a) the two new extension files (multimedia, MoF), (b) `occurrenceID` column
cross-references between occurrence.txt and extension rows that carry occurrenceID, (c)
multimedia.txt having at most one row per (identifier, occurrenceID) combination. Fatal
errors fail the export and mark `DataExport.status = FAILED`; warnings log.

### UI label

`ui/src/data-services/models/export.ts`:
- Add `'dwca'` to `SERVER_EXPORT_TYPES`
- Label: `"Darwin Core Archive (DwC-A) — April 2026 Draft"`

### Code organization (optional, leaning split)

`ami/exports/dwca.py` is 432 lines and will ~double. Proposal: split into
`ami/exports/dwca/` package with `fields.py` / `meta.py` / `eml.py` / `validator.py` /
`__init__.py`. Public surface unchanged. Ask user yes/no.

### Tests

- Update existing 10 DwCAExporterTests for the new extension shape (additions, not
  replacements — core is unchanged)
- Add tests per new extension: header parity, row counts, coreid referential integrity,
  MoF measurement-type coverage, multimedia-URL presence, multimedia-crop has
  occurrenceID populated, capture rows don't
- Add test: Event with no occurrences after filtering produces 0 extension rows but no
  error
- Add test: detection with no crop URL is skipped from multimedia

### PR discussion comment

Post a dedicated "Multimedia and bounding-box representation" comment on the PR
covering:
- Capture images vs detection crops: one-file-with-occurrenceID-column approach vs.
  two separate multimedia files (not possible in DwC-A — only one table per rowType).
- bbox in MoF vs. inline on multimedia row (MoF wins because structured numeric).
- How CamtrapDP will represent the same data (richer media.csv with structural link to
  detections).
- Solicit WG feedback; not blocking this PR.

### Device model changes — deferred

Note in PR follow-up section: `Device.device_type` and `Device.attractant_type` (and
`Device.light_wavelength`) should be added in the CamtrapDP PR. DwC has no direct term
for attractant; these will populate CamtrapDP `captureMethod` + custom columns on
event.txt in a later DwC-A iteration.

### Explicitly deferred

- CamtrapDP native export
- Device model additions
- Sensitive-taxa coordinate generalization
- Reverse-geocoding for country/state/locality
- `coordinateUncertaintyInMeters`
- Annotation / model-metadata extensions (CamtrapDP path)
- Online GBIF-API validator CI
- IPT publishing + DOI minting

---

## Open verification items

Before finalizing: fetch GBIF Camera Trap Data Publishing Guide and confirm:
- Current recommendation for DwC-A core (Event vs Occurrence)
- Canonical approach to linking detection media back to occurrences
- Any explicit patterns around absence/effort-preserving representation

If the guide contradicts the Event-Core direction, revisit. If it confirms or is silent,
proceed.

---

## Followups after verification

1. Fetch + summarize GBIF camera-trap guide findings in this file.
2. Update PR body with the Event-Core-retained rationale + absence-inference argument.
3. Write implementation plan via `writing-plans` skill.
4. Implement in order: extensions + field split + validator → EML 2.2.0 → UI label → tests → docs.
5. Post the multimedia discussion comment on the PR.
