# Algorithm results

An algorithm result (`ami/ml/models/algorithm_result.py`) is the standard record of what an
algorithm decided about one occurrence: the figures only that run knew, its headline `value`, and the
occurrence's determination before and after, with the algorithm and job that produced it. Any
algorithm can write one, whether a post-processing method or a pipeline step. It is a record, never an
input: the determination still comes only from identifications and classifications.

Each kind of result (`class_masking`, `size_filter`, and next `tracking` and `rank_rollup`) has its
own data model in `schemas.py` in this package. The occurrence history
(`ami/main/models_future/history.py`, `GET /occurrences/{id}/history/`) shows each result next to the
occurrence's identifications and predictions, and the API publishes each kind's data as a typed
OpenAPI component.

Outputs that belong to a single detection keep their own tables: classifications, and feature vectors
(`DetectionEmbedding`). They carry the same provenance (algorithm and job) but are not results.

This guide covers adding a result kind, using rank roll-up (draft #1361) as the example, and then
adding another kind of history entry. Adding a kind needs no migration, no serializer change and no
OpenAPI change: it touches the data model, the task that writes it, and the UI card.

## How results fit the post-processing framework

The post-processing framework (`ami/ml/post_processing/`) runs a method over data Antenna already has.
Algorithm results are its output side.

- **Input:** a task subclasses `BasePostProcessingTask` (`base.py`) with a `key`, a `name` and a
  pydantic `config_schema`, and is registered in `registry.py`. An admin action
  (`admin/actions.py`, `make_post_processing_action`) creates a `post_processing` job whose params are
  `{"task": <key>, "config": {...}}`. `PostProcessingJob.run` validates the config against the schema,
  stores the validated config (defaults included) back on the job, and runs the task with
  `self.job` and `self.algorithm` (one `Algorithm` row per method; class masking makes one per source
  classifier and species list).
- **Output:** what the task changes goes through the classifications it creates, each carrying its
  `job`, its `algorithm_result` and, when it replaces one, `applied_to`. What it decided about each
  occurrence goes into one algorithm result of the task's kind, written by `AlgorithmResultWriter` in
  the same transaction as each batch.
- **Shown together:** the history shows each result with the job's settings, labelled, ordered and
  linked from the same `config_schema`. One schema therefore describes a task's settings for
  validation, the admin form, the stored job and the result card.

Results are not tied to the framework. A pipeline step that decides something per occurrence can write
them the same way, with `AlgorithmResult.objects.record_many`.

A kind is not tied to a task either; today's two happen to be one each. A task can write several kinds
(one `AlgorithmResultWriter` per kind), and several tasks or pipeline steps can write the same kind and
share its data model and card. Each method keeps its own current result, because "current" is per
occurrence, algorithm and kind. The history labels settings from the job's task, not from the kind.
One rule when a run writes several kinds: pass the classifications it creates to only one writer's
`start_batch`, because `start_batch` points each of them at that writer's result for its occurrence.

## Adding a result kind

### 1. Describe the result's data

Add a pydantic model in `schemas.py` and list it in `ALGORITHM_RESULT_DATA_MODELS`.

```python
class RankRollupResultData(DeterminationSnapshot):
    """Figures from the occurrence's winning detection: the one whose rolled-up classification scores highest."""

    kind: ClassVar[str] = "rank_rollup"

    rolled_up_rank: str
    # The summed probability at the new rank; the result's value.
    rolled_up_score: float
    # The threshold that rank cleared.
    threshold: float
    # Whether the rolled-up taxon is an ancestor of the source classifier's taxon.
    within_lineage: bool
    # The best summed score at each rank tried, e.g. {"SPECIES": 0.41, "GENUS": 0.72}.
    rank_scores: dict[str, float] = {}


ALGORITHM_RESULT_DATA_MODELS = (ClassMaskingResultData, SizeFilterResultData, RankRollupResultData)
```

Rules for the model:

- **Record only what the run alone knows.** Settings belong on the job and are shown from there. The
  new taxon and score are on the classifications the run creates. The prediction a classification
  replaced is its `applied_to`, which the history shows as `replaced`. Do not copy any of these into
  `data`.
- **Subclass `DeterminationSnapshot`** if the run can change the determination. The writer fills
  `determination_before_id` and `determination_after_id`.
- **Keep fields flat.** Use scalars, lists and string-keyed dicts of scalars. A nested model or an
  `Enum` makes pydantic emit `#/definitions/...` references that do not resolve inside the OpenAPI
  schema; `ami/ml/results/tests.py` fails if a kind does.
- **Declare ids of other records with `reference()`**, for example
  `merged_into_id: int | None = reference("occurrence")`. The history returns such a field as
  `{type, id, name}` under `data_references`, and the UI links it. The type must be a key of
  `REFERENCE_TYPES` in `ami/main/models_future/references.py`. To add a type, add it there and add its
  route to `ROUTES` in `ui/src/utils/references.ts`. A guard test fails when a declared type has no
  mapping.
- **`extra`** (inherited) takes anything else the method returns. Nothing may read it for logic; when
  a feature needs a value from it, make that value a typed field.
- **Pick one figure as the result's `value`:** the number lists sort and filter on (here
  `rolled_up_score`). It is not necessarily a confidence; for tracking it is a motion figure.

The kind's OpenAPI component (`RankRollupResultEntry`) and its enum name come from the registry
automatically.

### 2. Describe the task's settings

The task's config schema (the pydantic model `config_schema` on the task) is where the history gets
each setting's label, order and referenced record. Give every field a `title`, and declare ids with
`reference()`:

```python
from ami.ml.results.schemas import reference


class RankRollupConfig(pydantic.BaseModel):
    source_image_collection_id: int | None = reference("capture_set", None, title="Capture set")
    occurrence_id: int | None = reference("occurrence", None, title="Occurrence")
    thresholds: dict[str, float] = pydantic.Field(DEFAULT_THRESHOLDS, title="Thresholds by rank")
    rollup_order: list[str] = pydantic.Field(DEFAULT_ORDER, title="Ranks to try, in order")
```

A field without a `title` shows its key on the result card. Register the task in
`ami/ml/post_processing/registry.py`; the history finds the schema through the job's
`params["task"]`.

### 3. Write results from the task

Use `AlgorithmResultWriter` (`ami/ml/results/writer.py`), the same way the size filter and class
masking do. The writer creates one result per occurrence per run, in the same transaction as the
batch that changes the occurrence, so a batch never lands without its record.

```python
results = AlgorithmResultWriter(
    kind=RankRollupResultData.kind,
    algorithm=self.algorithm,
    job=self.job,
    value_field="rolled_up_score",
)

for classification in scope:  # batched; see class_masking.py for the batching and progress pattern
    ...
    if rolled_up:
        new = Classification(
            detection=classification.detection,
            taxon=winner,
            score=summed_score,
            terminal=True,
            algorithm=self.algorithm,
            applied_to=classification,  # the prediction this one replaces
            job=self.job,
            timestamp=classification.timestamp,
        )
        classification.terminal = False  # demote only the classification this run replaced
        to_create.append(new)
        to_demote.append(classification)
        occurrences.add(classification.detection.occurrence)
        # The occurrence's result keeps the figures of its highest-ranked detection.
        results.note(classification.detection.occurrence, figures, rank=summed_score)

def flush():
    with transaction.atomic():
        results.start_batch(occurrences, to_create)  # creates results; points the new rows at them
        Classification.objects.bulk_create(to_create)
        Classification.objects.bulk_update(to_demote, ["terminal"])
        for occurrence in occurrences:
            occurrence.save(update_determination=True)
        results.finish_batch(occurrences)  # records the determination after the saves
```

Rules for the writer:

- **Call `note()` before `start_batch()` for every occurrence in the batch.** `start_batch` reads the
  noted figures, and the figures must contain `value_field`.
- **Set `applied_to`** on a classification that replaces another. The history then marks the replaced
  prediction as superseded by this run and shows it as the result's original prediction. A
  classification that replaces nothing (like the size filter's "Not identifiable") instead supersedes
  terminal predictions it outranks on the same detection.
- **Demote only what the run replaced.** Demoting other classifiers' rows leaves predictions in the
  history that look superseded with nothing saying why.
- **Set `job=self.job`** on every row the run creates.
- **Do not call `.distinct()`** on a classification queryset that includes the `scores` or `logits`
  arrays; de-duplicating sorts the arrays (see #1376).
- **One current result per occurrence, algorithm and kind.** A re-run replaces the current result and
  keeps the old one as history. When results from different sources should coexist (masking a second
  classifier, say), give each source its own `Algorithm`, as class masking does.
- **Occurrences without a project** get no result and a warning; the run carries on (#1188).

### 4. Show it in the UI

- `ui/src/data-services/models/occurrence-history.ts`: add the data interface (mirroring the pydantic
  model), the entry type (`ServerResultEntry<'rank_rollup', RankRollupResultData>`) to the
  `AlgorithmResultEntry` union, and the kind to `ALGORITHM_RESULT_KINDS`. Until the kind is in that
  list, the timeline skips its results, so the server side can ship first.
- `ui/src/pages/occurrence-details/identification-card/algorithm-result.tsx`: add an icon and label
  to `KINDS`, and a `case` in the stats switch for the kind's own figures. The determination row, the
  new prediction with its Confirm button, the original prediction (from `replaced`), the detections
  changed, the settings and the job row are shared by every kind.
- `ui/src/utils/language.ts`: add the strings the card uses.

### 5. Test it

- The run writes one result per touched occurrence, with the expected `data` and `value`.
- Each created classification has `algorithm_result` and `job` set, and `applied_to` where it
  replaced one.
- The history shows the result with its classifications, the replaced prediction as superseded, and
  `replaced` filled.
- A second run makes the first result history (`is_current` false).
- An occurrence with several affected detections gets one result, with the figures of the
  highest-ranked detection.
- `python manage.py test ami.ml.results ami.main.test_occurrence_history` covers the registry guards
  and the history contract.

### What you do not need to touch

- **Migrations:** `kind` is a plain `CharField` without `choices`; every write path validates `data`
  against the registry instead.
- **Serializers and OpenAPI:** the history serializer and the `oneOf` union are generated from the
  registry, including `SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"]`.
- **The determination:** it never reads results.

## Adding another kind of history entry

The history merges entries from several tables: algorithm results, identifications and predictions.
Another source, such as the feature vectors a pipeline added to an occurrence's detections, becomes a
new entry type rather than a result kind when it records an output and not a decision. Add it in five
places:

1. **`ami/main/models_future/history.py`:** a section of fields on `OccurrenceTimelineEntry` (if the
   shared fields are not enough), and a loader in `occurrence_timeline` that adds the entries with a
   fixed number of queries, whatever the occurrence's size. Entries with a `job` get its settings
   automatically. For vectors, group by job and algorithm, and never select the vector column:
   ```python
   DetectionEmbedding.objects.filter(detection__occurrence=occurrence)
       .values("algorithm", "job", "key")
       .annotate(detections=Count("detection", distinct=True), timestamp=Max("timestamp"))
   ```
2. **`ami/main/api/serializers.py`:** an `<Name>EntrySerializer(HistoryEntryBaseSerializer)` with
   `type = serializers.ChoiceField(choices=["<type>"])` and its own fields. Add it to the serializers
   of `OCCURRENCE_HISTORY_ENTRY_SCHEMA` and to `HISTORY_ENTRY_SERIALIZERS`.
3. **`config/settings/base.py`:** a `"<Name>EntryTypeEnum": ["<type>"]` entry in
   `SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"]`, so the literal `type` gets a readable enum name.
4. **The UI:** the entry interface in `ui/src/data-services/models/occurrence-history.ts`, added to
   `ServerOccurrenceHistoryEntry` and to `TimelineItem`, with a `case` in `getTimelineItems`; a card
   component in `ui/src/pages/occurrence-details/identification-card/`, rendered in
   `occurrence-timeline.tsx`. `getTimelineItems` skips entry types it does not know, so the server
   side can ship first.
5. **Tests in `ami/main/test_occurrence_history.py`:** the new entries in the endpoint response, the
   strict `HISTORY_QUERIES` count raised by the loader's queries (and still the same at two history
   sizes), and the new component in the OpenAPI union.
