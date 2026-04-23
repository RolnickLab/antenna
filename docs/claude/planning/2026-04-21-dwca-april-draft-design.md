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

## GBIF guide findings (2026-04-21)

Two GBIF guides give **opposite** recommendations for camera-trap data. Resolving the
tension in AMI's favor:

### Camera-Trap Data Publishing Guide — Occurrence Core + AMDE

Recommends Occurrence Core + Audubon Media Description extension. Reason per the guide
itself: GBIF portal's UI can't display event-level media when viewing an individual
occurrence (confirmed by GBIF portal-feedback issue #4216). The guide's own rationale
acknowledges Model 2 (Event Core + Occurrence + AMDE) is "conceptually superior" but is
not recommended because of portal display limitations.

The guide explicitly says **"classifications of blanks, vehicles and preferably humans
should be filtered out"** — i.e. it does not support absence representation. This
directly sacrifices AMI's core scientific contribution (automated monitoring's
strongest claim is *provable absence during a known sampling window*).

### Survey & Monitoring Publishing Guide + Humboldt Extension — Event Core

The Humboldt Extension (ratified 2024-2025, 55 terms) is **explicitly an Event-Core
extension**: "a vocabulary extension to the Darwin Core Event Class." It is the
GBIF-official pathway for survey and monitoring data.

Terms relevant to AMI, all on event rows:

- `eco:isSamplingEffortReported` = true
- `eco:samplingEffortValue` + `eco:samplingEffortUnit` — e.g. value=`1440`, unit=`camera-minutes` or trap-nights
- `eco:samplingEffortProtocol` — free text: "automated camera trap, image interval 10s, continuous overnight monitoring"
- `eco:isAbsenceReported` = true
- `eco:targetTaxonomicScope` — v1: derived from `Project.default_filters_include_taxa`
  (lowest common ancestor across the M2M; blank if none). v2: sourced from the `TaxaList`
  curated per Site (`Site.primary_taxa_list`, falling back to `Project`'s default "all
  possible species" list). The TaxaList is the enumerable scope that later unblocks
  per-taxon absence occurrences.
- `eco:inventoryTypes` = "trap or sample"
- `eco:protocolNames` / `eco:protocolDescriptions` — document the ML pipeline as a protocol
- `eco:hasMaterialSamples` = true, `eco:materialSampleTypes` = "digital images"

Absence pattern (canonical): per-taxon absence `Occurrence` row per Event with
`dwc:occurrenceStatus = "absent"` and eventID link. AMI can emit absence occurrences in
a follow-up PR once `project.target_taxa` is defined. For this PR, we declare
`eco:isAbsenceReported=true` on events to signal the capacity; actual absence rows come
later.

### Decision (confirmed after research)

**Event Core + Humboldt Extension + Occurrence + Multimedia + MeasurementOrFact.**
Matches the GBIF survey-data guide and the extension purpose-built for our data shape.
Trades GBIF portal display of media at the occurrence view (a UI limitation, not a
data-ingestion limitation) for preserving absence inference and structured sampling
effort.

The camera-trap guide's Occurrence-Core recommendation is a pragmatic workaround for
GBIF's portal UX, not a statement of correct data modeling for monitoring data. AMI is
a survey/monitoring dataset first, a camera-trap records dataset second.

### CamtrapDP positioning

The camera-trap guide explicitly recommends CamtrapDP as the primary format; GBIF
doesn't yet ingest CamtrapDP in production. So CamtrapDP is still the right next-PR
target, but for AMI's community (Wildlife Insights, Agouti, EU camera-trap networks)
rather than as a GBIF ingestion route. DwC-A via Humboldt remains the GBIF path.

---

## Updated archive shape

```
project_export.zip
├── meta.xml
├── eml.xml                       ← EML 2.2.0
├── event.txt                     ← Event Core (DwC Event terms + Humboldt eco: terms)
├── occurrence.txt                ← Occurrence extension (coreid=eventID)
├── multimedia.txt                ← GBIF Multimedia ext (coreid=eventID; occurrenceID column
│                                    links detection crops back to occurrences)
└── measurementorfact.txt         ← MoF extension (coreid=eventID; occurrenceID column for
                                     per-occurrence/per-detection measurements)
```

`event.txt` carries the Humboldt `eco:` terms as additional columns. They're declared in
meta.xml via their term URIs. Humboldt is technically registered as its own extension
(`http://eco.tdwg.org/xml/ecoterm.xml`), but there's precedent for flattening Humboldt
terms into the Event Core row; GBIF accepts both. We flatten for simplicity — fewer
files, same semantic content, same GBIF ingestion outcome.

---

## Sources consulted

- GBIF Camera Trap Data Publishing Guide (docs.gbif.org/camera-trap-guide/en/) — §4.3,
  §4.4.1, §4.4.2, §4.4.3; recommends Occurrence Core + AMDE as portal-pragmatic.
- GBIF Survey & Monitoring Data Publishing Guide (docs.gbif.org/guide-publishing-survey-data/en/)
  — recommends Event Core + Humboldt.
- GBIF Survey & Monitoring Quick-Start Guide (docs.gbif.org/survey-monitoring-quick-start/en/)
  — Humboldt term-by-term usage.
- GBIF portal-feedback issue #4216 — confirms Event-level multimedia is "conceptually
  superior" but GBIF portal UI doesn't display it in occurrence views.
- Humboldt Extension Implementation Experience Report (eco.tdwg.org).

---

## Followups after design approval

1. Update PR body with Event-Core-retained + Humboldt rationale.
2. Write implementation plan via `writing-plans` skill.
3. Implement: extensions + Humboldt terms on event.txt + split `dwca.py` → package →
   validator extensions → EML 2.2.0 → UI label → tests → docs.
4. Post the multimedia/bbox discussion comment on the PR (now more concrete: GBIF
   portal-display caveat is a known trade, not a surprise).
