# Biodiversity, citizen-science and annotation platforms: machine predictions vs human verification

**Question.** An insect-monitoring platform wants (a) a home for machine outputs that are not a
species label (feature vectors, logits, tracking and filter decisions) with provenance, and (b) a
human "review" record per target (occurrence, detection, image) and aspect (identification,
grouping, bounding box, count), so any model output can be evaluated against what a person
verified. How do comparable platforms and standards model this?

**Produced by.** A research agent (Claude Sonnet), 2026-09-29, supervised. Most pages were
fetched directly; several platforms could not be read and are listed at the end.

## 1. Camera-trap platforms

- **Wildlife Insights**: each image stores only its most recent identification; `identified_by`
  holds a user name or the literal "Computer Vision", and `cv_confidence` holds the model score.
  No history, no per-class scores. Sequences are images within 60 seconds.
  https://wildlifeinsights.org/node/3079
- **TRAPPER**: the closest match. One Classification table with four types: AI, USER, FEEDBACK
  (post-approval correction) and FINAL. Exactly one FINAL per (resource, project), carrying
  `is_approved` and a `source_classification` pointer to the AI or USER row that was approved.
  The AI row is never overwritten; approval and forking are foreign-key rewrites.
  https://trapper-project.readthedocs.io/en/docs-docs-refactor/explanation/classification-model/
- **Agouti**: project, deployment, sequence, observation. Human review is a "validated" flag on
  the sequence, exported. The docs do not say how an AI observation is told apart from a human
  one. https://docs.agouti.eu/using/validate.html
- **MegaDetector batch JSON**: per image, `detections[]` with `category`, `conf`, normalised
  `bbox`; classifications as `[class_id, confidence]` pairs sorted descending; an `info` block
  with detector and classifier metadata. No human-label concept.
  https://github.com/agentmorris/MegaDetector/blob/main/megadetector-output-format.md
- Timelapse, Zamba, EcoAssist, Camelot, eMammal, TrapTagger: no usable sources.

## 2. Identification platforms

- **iNaturalist**: one active identification row per user per observation; rows can be
  withdrawn and the API filters them with `current=true|false|any`; categories leading,
  improving, supporting, maverick. The community taxon is computed from the rows, not stored as
  an input. https://help.inaturalist.org/en/support/solutions/articles/151000170241,
  https://forum.inaturalist.org/t/searching-for-withdrawn-identifications/28929
- **iNaturalist computer-vision suggestions are not stored**; they are generated on demand so
  users always get the latest model, which means the model cannot be evaluated retroactively.
  https://forum.inaturalist.org/t/downloading-ai-suggested-ids-for-observations/49559/6
- **Zooniverse**: each classification is a raw per-volunteer row with annotations and a
  `workflow_version`; consensus is produced afterwards by extractors and reducers, keyed by
  subject, workflow and task, kept separate from the raw rows.
  https://help.zooniverse.org/next-steps/data-exports
- **Pl@ntNet**: two GBIF datasets, one human-validated and one automatically identified;
  validation is a dataset-level split. https://inpn.mnhn.fr/espece/cadre/54846?lg=en
- **Observation.org**: automated validation assists validators; experts keep final authority;
  validation is a status on the record. https://observation-international.org/en/

## 3. Standards

- **Darwin Core**: Identification is its own class (`identifiedBy`, `identifiedByID`,
  `dateIdentified`, `identificationVerificationStatus`, `identificationQualifier`,
  `identificationRemarks`, `identificationID`); an occurrence can have many identifications;
  `basisOfRecord=MachineObservation` marks the whole record, not one identification.
  https://dwc.tdwg.org/terms/
- **Camtrap DP observations**: `observationLevel` is `media` or `event`; `classificationMethod`
  is `human` or `machine`; `classifiedBy`, `classificationTimestamp`, `classificationProbability`
  (0–1), `bboxX/Y/Width/Height` (0–1 relative), `count`, `eventID`, `mediaID`. Media-level
  observations may have several classifications per media; event-level observations must be
  mutually exclusive so counts can be summed. One row is one classification, so machine and human
  rows coexist for the same media. https://camtrap-dp.tdwg.org/data/
- **W3C Web Annotation**: body, target, motivation (identifying, classifying, assessing); a
  target can be another annotation, the cleanest general pattern for a review that points at a
  model output. https://www.w3.org/TR/annotation-model/
- **W3C PROV-O**: Entity, Activity, Agent; `wasGeneratedBy`, `wasAttributedTo`, `wasDerivedFrom`,
  `used`; revision and invalidation are first-class. https://www.w3.org/TR/prov-o/
- Audubon Core: not researched.

## 4. Annotation and evaluation tools

- **Label Studio**: each task has separate `predictions[]` and `annotations[]`; predictions are
  read-only and carry `model_version` and `score`; predictions can be copied into annotations.
  https://labelstud.io/guide/predictions
- **FiftyOne**: a sample holds several label fields (`ground_truth`, `predictions`);
  `evaluate_detections(pred_field, gt_field, eval_key, iou)` writes per-object `<eval_key>`
  (tp/fp/fn), `<eval_key>_id` and `<eval_key>_iou`; `to_evaluation_patches(eval_key)` gives a
  view for inspection. https://docs.voxel51.com/user_guide/evaluation/detections.html
- CVAT, Encord, Roboflow: not researched.

## What transfers to Antenna

1. Append-only outputs, separate review rows (TRAPPER): never edit the machine row; store the
   review as its own row pointing to the output it judged, so evaluation is one join.
2. Review row shape: target, aspect, verdict (confirmed, rejected, corrected), the corrected
   value, reviewer, timestamp, the reviewed output id, a withdrawn or superseded flag. One
   active row per reviewer and target, history kept (iNaturalist).
3. Derived current state: compute the "current answer" from review rows (iNaturalist,
   Zooniverse); if cached, use a pointer like TRAPPER's FINAL `source_classification`.
4. Keep full class scores: Wildlife Insights and MegaDetector keep only the top result or top-k;
   iNaturalist's on-demand approach shows what is lost by not storing outputs.
5. Provenance on every output: algorithm and version, run and job id, input ids; PROV vocabulary;
   Label Studio's `model_version`. Reviews carry the same agent fields.
6. Camtrap DP export: machine output → `classificationMethod=machine`, `classifiedBy=<algorithm
   + version>`, `classificationProbability=top score`, timestamp; human review →
   `classificationMethod=human`, `classifiedBy=<reviewer>`; occurrence rows →
   `observationLevel=event` with `eventID`; detection rows → `observationLevel=media` with
   `mediaID` and bbox in 0–1. No place for tracking decisions, vectors or logits.
7. Darwin Core export: review → `identificationVerificationStatus`, `identifiedBy`,
   `dateIdentified`, `identificationRemarks`; `basisOfRecord=MachineObservation` only when no
   human identification exists.
8. Naming: prediction / output for machine, review for human (Label Studio). Avoid
   "annotation", which Zooniverse uses for raw volunteer answers.
9. Grouping and bbox reviews need a stable target: keep a target-type column and a frozen
   reference to the exact detection set reviewed, so a later re-tracking does not invalidate old
   reviews.

## Could not verify

FiftyOne field names beyond the docs summary; the Darwin Core term for a "current"
identification; Wildlife Insights, Timelapse, Zamba, EcoAssist, Camelot and eMammal internals
and whether Wildlife Insights keeps any history; TrapTagger's schema; the Zooniverse aggregation
developer page (host unreachable); Pl@ntNet and Observation.org per-record data models; CVAT,
Encord, Roboflow, Audubon Core.
