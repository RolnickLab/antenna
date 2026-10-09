# Algorithm results

An algorithm result (`ami/ml/models/algorithm_result.py`) records what one run of a method decided
about one occurrence: the figures only that run knew, a headline `value`, and the occurrence's
determination before and after, with the algorithm and job that produced it. Post-processing tasks
write them today. The determination never reads them; it still comes only from identifications and
classifications. The occurrence history (`ami/main/api/occurrence_history/`,
`GET /occurrences/{id}/history/`) shows each result with the classifications its run created.

Processing services cannot write results: their contract (`ami/ml/schemas.py`) has no place for them
and must not name occurrences, which Antenna creates. Classifications and feature vectors keep their
own tables, with the same algorithm and job provenance.

## Adding a kind

1. **Data model** in the task's module, beside its config schema (`ClassMaskingResultData` in
   `class_masking.py`), subclassing `AlgorithmResultData` from `schemas.py`. Set `kind` and
   `value_field` (the figure lists filter and sort on; every write copies it into `value`).
   Subclass `DeterminationSnapshot` if the run can change the determination. Record only what the
   run alone knows: its config stays on the job, the new taxon on the classifications it creates, and
   the prediction it replaced on their `applied_to`. Anything else the method returns goes in
   `extra`, which nothing reads for logic.
2. **Task**: declare the model in the task's `result_models` (which registers the kind), give every `config_schema` field a
   `title`, and declare fields that hold a record id with `model_reference("capture_set", ...)`
   (`ami/base/model_references.py`); `ami/jobs/job_config.py` labels and links them. A new reference type
   is declared on its model (`reference_type`, `reference_name_field`) and routed in
   `ui/src/utils/model-references.ts`.
3. **Writing**: use `AlgorithmResultWriter` (`writer.py`) as `class_masking.py` and
   `small_size_filter.py` do. Per batch, inside one transaction: `note()` each changed detection's
   figures, `start_batch()` before inserting classifications (it points them at their result), then
   save the occurrences and call `finish_batch()`.
4. **UI**: add the data interface and the kind to `ui/src/data-services/models/occurrence-history.ts`
   and a stats case to `ui/src/pages/occurrence-details/history/algorithm-result.tsx`.
   The timeline skips kinds it does not know, so the server side can ship first.
5. **Tests**: one result per touched occurrence with the expected `data` and `value`; created
   classifications carry `algorithm_result`, `job` and, where they replaced one, `applied_to`; the
   history shows the result. `python manage.py test ami.ml.results ami.main.api.occurrence_history.tests`.

No migration, serializer or OpenAPI change is needed: `kind` is a plain `CharField`, every write path
validates `data` against the registry, and the API publishes `data` as JSON.

## Rules

- **Results are only added.** Each run adds one result per occurrence it touches; running a method
  twice leaves two. A retried job reuses its own results. A list that needs an algorithm's latest
  value takes the latest by timestamp.
- **A run gets its own `Algorithm` only when it changes what can be output.** Class masking makes one
  per source classifier and species list, because the list changes which species can be named. The
  rest of the config stays on the job: the size filter uses one algorithm whatever its threshold.
- **Demote only what the run replaced**, set `job` on every row it creates, and never call
  `.distinct()` on a classification queryset that includes the `scores` or `logits` arrays (#1376).
- **Occurrences without a project** get no result and a warning; the run carries on (#1188).
- **A result belongs to an occurrence.** Class masking and the size filter work per detection, so a
  result keeps the figures of one detection per occurrence: the winning one for masking, the smallest
  flagged one for the size filter. Running these methods before occurrences exist, inside the
  pipeline, needs a detection target first.
