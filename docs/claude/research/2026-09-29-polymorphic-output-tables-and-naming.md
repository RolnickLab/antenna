# Per-target tables vs one polymorphic table for model outputs, and what to call them

**Question.** For model-output rows that share one shape (algorithm, run, key, timestamp,
numeric array, JSON payload) but point at different targets (detection, occurrence, image,
taxon): one table per target on an abstract base, or one physical table with nullable foreign
keys to each target plus a denormalised project column and a check that exactly one is set?
Rows will number in the millions for per-detection embeddings and far fewer per occurrence. What
do comparable systems call these things?

**Produced by.** A research agent (Claude Sonnet), 2026-09-29, supervised. Sources were fetched
through summarising tools; thin pages are flagged under "Could not verify".

## 1. Relational guidance on "exactly one of N foreign keys"

- Karwin's *SQL Antipatterns* ("Polymorphic Associations") treats a type-string plus id column
  (the Rails/Django generic-relation shape) as an antipattern: it cannot carry a real foreign
  key. Fixes: reverse the reference, one intersection table per parent, or a common super-table.
  https://www.oreilly.com/library/view/sql-antipatterns/9781680500073/ (search snippets only)
- Hashrocket recommends an "exclusive belongs-to" (exclusive arc): one nullable FK per target
  and a CHECK that exactly one is set. Pros: real referential integrity, no orphans, nulls cost
  about a bit per row. Index advice: partial unique indexes on each non-null column.
  https://hashrocket.com/blog/posts/modeling-polymorphic-associations-in-a-relational-database
- PostgreSQL `num_nonnulls()` expresses the check: `CHECK (num_nonnulls(a, b, c) = 1)`.
  https://jakeworth.com/posts/postgresql-polymorphism/
- Fowler's Class Table Inheritance (PoEAA ch. 12): one table per class in the hierarchy; the
  catalog page gives no trade-offs. https://www.martinfowler.com/eaaCatalog/classTableInheritance.html

## 2. Django specifics

- `GenericForeignKey`: no DB constraint, cannot be filtered or joined on directly, returns None
  when the target is deleted, no automatic index (the docs recommend a manual
  `Index(fields=["content_type", "object_id"])`). https://docs.djangoproject.com/en/5.1/ref/contrib/contenttypes/
- `UniqueConstraint(condition=Q(...))` gives partial uniques; `CheckConstraint` takes a Q or
  expression; constraint names on abstract bases need `%(app_label)s_%(class)s` templating.
  https://docs.djangoproject.com/en/5.1/ref/models/constraints/
- The exclusive-arc check can be written as a `CheckConstraint` using
  `Func(..., function="num_nonnulls")`; no worked example verified.
- Wagtail avoided generic foreign keys for reporting that needs permission filtering; page logs
  get their own model, and complex cases subclass `BaseLogEntry` for their own log model.
  https://docs.wagtail.org/en/latest/extending/audit_log.html.md
- Every access to a GFK target costs a query unless prefetched.
  https://medium.com/django-unleashed/generic-foreign-keys-in-django-managing-relationships-with-polymorphism-0faa6f9c6e57
- Sentry, Zulip, django-activity-stream: not verified.

## 3. Naming in comparable systems

- MLflow: Run, Metric, Param, Artifact, Tags; the Run is the execution row.
  https://mlflow.org/docs/latest/ml/tracking/
- OpenLineage: Job (definition), Run (execution, keyed by UUID), Dataset.
  https://openlineage.io/docs/spec/object-model/
- PROV-O: Entity, Activity, Agent; `wasGeneratedBy`, `used`, `wasAttributedTo`. An Activity
  produces an Entity; the output is not named by its target. https://www.w3.org/TR/prov-o/
- Label Studio: Prediction (model output, read-only, `model_version`) and Annotation (human) are
  separate objects, named by producer type. https://labelstud.io/guide/predictions
- FiftyOne: label fields `ground_truth` and `predictions`; evaluations use an `eval_key`.
  https://docs.voxel51.com/user_guide/using_datasets.html#labels
- Camtrap DP: a single Observation record with `classificationMethod` (human or machine),
  `classifiedBy`, `classificationProbability`, `classificationTimestamp`. https://camtrap-dp.tdwg.org/data/

Across all of these the noun is named by producer or role (run, prediction, annotation,
activity) and the target is a reference. None uses a "<Target>Output" noun.

## 4. Storage and performance

- TOAST triggers when a row exceeds about 2 KB; large values move out of line behind an 18-byte
  pointer; an UPDATE incurs no TOAST cost if the out-of-line values are unchanged. Small rows stay
  dense in the heap. https://www.postgresql.org/docs/16/storage-toast.html
- A float array of 768 or more dimensions exceeds 2 KB and will TOAST; shorter arrays stay inline
  and widen heap rows.
- Hot rows (per-occurrence decisions read on a page) and cold rows (embeddings) in one table share
  heap pages, indexes and autovacuum scheduling. Blog sources claim TOAST bloat scales with
  updates, which contradicts the docs quote when the array is unchanged; treat as unproven.
  https://www.netdata.cloud/guides/postgres/postgres-toast-table-bloat/
- HOT updates need the new tuple to fit on the same page and no indexed column to change; wide
  rows reduce that headroom. https://khmousa.medium.com/understanding-heap-only-tuples-hot-in-postgresql-a334b9adbc0a
- An append-only embeddings table is insert-mostly and needs little vacuum work beyond freezing
  and visibility-map setting.

## Recommendation for this platform

A hybrid closer to per-target tables: a split by workload, not a nullable-FK superset.

- Per-detection arrays: their own table with a real non-null FK to Detection, an index on
  (detection, algorithm), a unique on (detection, algorithm, key), and a denormalised `project`
  only if permission filters need it (Wagtail's reasoning).
- Occurrence-level outputs: a separate table; volume, hotness and read patterns differ, and every
  FK stays non-null and enforced.
- Reject the exclusive arc as the default for the big table: defensible for integrity, but it
  puts millions of cold wide rows and few hot rows in one heap, needs one partial index per
  target, and adds a nullable column per new target.
- An abstract base for the shared columns; avoid Django multi-table inheritance (a join to a
  millions-of-rows table); use `%(class)s` in constraint names.

Suggested names: abstract base `AlgorithmOutput`; per-target tables `DetectionOutput` and
`OccurrenceOutput` (avoid "Prediction", because embeddings are not predictions); run row
`AlgorithmRun` or `InferenceRun` (the OpenLineage/MLflow Run, the PROV Activity); human review
`Review`, or `Annotation` for the Label Studio vocabulary, per target if reviews target detections
and occurrences differently. Keep the producer split explicit, as Label Studio and Camtrap DP do.

*Design outcome (recorded by the supervising session):* the per-target split was adopted for
embeddings; the occurrence-level table became a single polymorphic `AlgorithmResult` with a
denormalised `project`, because its rows are few and hot, so the volume argument does not apply;
the run row became `Job`; the human record is `OccurrenceReview`. The names `DetectionOutput` and
`OccurrenceOutput` were rejected by the owner as describing the foreign key rather than the thing.

## Could not verify

Exact wording of Karwin's chapter and Fowler's CTI trade-offs; how Sentry, Zulip and
django-activity-stream model records about several object types; a worked Django
`CheckConstraint` with `num_nonnulls`; a PostgreSQL 16 benchmark of hot and cold rows in one
table vs split, and whether TOAST bloat happens when the array is unchanged; Postgres community
advice specifically on exclusive arc vs CTI beyond the two posts cited.
