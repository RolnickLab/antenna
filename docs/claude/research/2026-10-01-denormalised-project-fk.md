# A denormalised `project` foreign key across many child models

**Question.** Antenna's chain is Project → Deployment → SourceImage → Detection →
Classification, with Occurrence and Event beside it. Some child models carry a copied
`project` FK; others reach it through a path and a `project_accessor` used for permission
filtering. More tables that need the column are coming. Part 1: what the codebase does today to
keep the copies in sync and where it has gone wrong. Part 2: Django and database strategies for
a denormalised tenant column across many tables.

**Produced by.** A research agent (Claude Sonnet), 2026-10-01, supervised; read-only on the
repository, no database queries. The drift measurement at the end was run afterwards by the
supervising session on a copy of the production database.

## Part 1: what Antenna does today

**Models carrying their own `project` FK.** Event, SourceImage, Occurrence and Deployment, all
in `ami/main/models.py`; all `SET_NULL`, nullable and indexed.

**Models that reach the project through a path.** Classification
(`detection__source_image__project`), Detection (`source_image__project`), Identification
(`occurrence__project`), SourceImageUpload (`deployment__project`), the jobs log model
(`job__project`). `project_accessor` only drives permission filtering
(`ami/base/models.py`, `get_project_accessor`); it populates and validates nothing.

**How the copies get filled: no signals, no DB triggers.**
- SourceImage: `update_calculated_fields()` sets `project` from `deployment` if it is empty;
  runs from `save()` and explicitly in the S3 import path before `bulk_create`, so bulk safety
  depends on that caller remembering.
- Event: the same fill-if-empty logic.
- Occurrence: created with `project=self.source_image.project` in
  `Detection.associate_new_occurrence` and in the pipeline results saver; management commands set
  it by hand.
- Propagation on a project change: `Deployment.save()` calls `update_children()`, which does
  `.exclude(project=self.project).update(project=...)` for Event, Occurrence and SourceImage with
  a warning log. The background-task version is commented out as not working.
- Gaps: the fill is "if empty" only, so a wrong non-null value is never corrected unless the
  deployment is saved; `.update()` skips signals; Jobs, collections and exports are not touched.

**Repair and move tooling.**
- PR #1192 (open), `move_project_data`: moves deployments and child data between projects; notes
  that bulk `.update()` bypasses `post_save` and offers a `--fire-post-save` flag; known
  leftovers: `DataExport.project_id` stays on the source, the source's `Project.taxa` is not
  pruned.
- PR #1188 (open), `check_data_integrity`: a framework with `get_*` and `reconcile_*` pairs; its
  only check today is occurrences without a determination; the natural home for a
  project-mismatch check.
- `fix_missing_relationships.py` exists under `ami/main/management/commands`; not read.

**Drift history.** No issue or commit about a wrong-project bug was found; the log hits are
`project_id` request parameters (#1390, #1133) and PR #1192's motivation. The only evidence is the
defensive code in `update_children()` whose warning says rows "have alternate projects set".

**Where the missing column costs today.**
- Detection has no `project` column, so project-scoped counts sequentially scan the whole
  detection table (about 641k rows) for every project size: about 1.8 s, 0.6 s and 0.5 s for
  large, mid and small projects (internal measurement, 2026-09-02). Proposed fix: denormalise
  onto Detection or use estimated counts (#1328).
- "Algorithms used in project X" seq-scans both classification and detection tables.
- PR #1133 (open): require `project_id` on list endpoints to prevent full table scans.
- The embeddings table on the tracking branch uses `project_accessor =
  "detection__source_image__project"`: every per-project vector query is three hops with no index
  leading with project.

## Part 2: strategies

**Django side.**
- `GeneratedField` cannot derive `project`: expressions "only reference fields within the model
  (in the same database table)". https://docs.djangoproject.com/en/5.2/ref/models/fields/#generatedfield
- `bulk_create`, `bulk_update` and `QuerySet.update()` skip `save()` and send no signals, so a
  `save()` override or `pre_save` signal alone does not cover bulk writes.
  https://docs.djangoproject.com/en/5.2/ref/models/querysets/#bulk-create
- Antenna's existing answer is an explicit derive step before bulk insert. A custom manager
  wrapping `bulk_create` to fill `project_id` is possible but unverified.
- django-computedfields: cross-table dependency resolution and bulk handling via
  `update_dependent`; PyPI says tested with Django 3.2 and 4.2. https://pypi.org/project/django-computedfields/
- django-denorm, FieldTracker, django-lifecycle: status not verified.

**Database side.**
- Composite FK: `UNIQUE (id, project_id)` on the parent, then `FOREIGN KEY (parent_id,
  project_id) REFERENCES parent (id, project_id)`. Postgres needs the referenced columns to be a
  non-deferrable unique or primary key or a non-partial unique index.
  https://www.postgresql.org/docs/16/sql-createtable.html
- `ON UPDATE CASCADE` copies a changed parent `project_id` into children. `ON DELETE SET NULL
  (col)` with a column list exists since Postgres 15 and avoids nulling the project column;
  column subsets are allowed only for ON DELETE.
- Tenant-scoped composite FKs make cross-tenant references impossible, with tenant-leading
  composite indexes the norm; plain ON DELETE SET NULL breaks.
  https://www.postgresql.org/message-id/CAF%2B2_SHQtbxWJe1CGwi6iOgMihorgo3Bt-x%2BPhSia%3Dgm5Qcr-g%40mail.gmail.com
- Django 5.2 added `CompositePrimaryKey` (https://docs.djangoproject.com/en/5.2/releases/5.2/);
  whether `ForeignKey` can target such a model could not be confirmed (recollection: no). The
  realistic route is plain Django FKs plus the composite constraint added with `RunSQL`.
- BEFORE INSERT fill trigger and AFTER UPDATE cascade trigger: standard Postgres, no cited source,
  untested.

**Multi-tenant practice.**
- Citus puts the distribution column in every table and in primary keys (`primary key
  (tenant_id, event_id)`) and co-locates equal values. https://docs.citusdata.com/en/stable/sharding/data_modeling.html
- A cross-project issue describes denormalising `realm_id` as costing "a migration and a
  backfill" and a value that "can drift from its parents" (not Zulip's own statement).
  https://github.com/ferriskey/ferriskey/issues/1441
- Nothing found on Sentry's `organization_id`; django-tenants is schema-per-tenant, so no column.

**Consistency checking.** Antenna already has the frame: PR #1188 `check_data_integrity`. A
project-mismatch check is a join per model: `child.project_id <> parent.project_id`, plus a null
count. A DB constraint makes it unnecessary for new tables.

## Recommendation for Antenna

1. New tables (embeddings, algorithm results, measurements, result batches): real `project` FK,
   NOT NULL from creation, project leading every composite index.
2. Enforce in the DB: `UNIQUE (id, project_id)` on parents plus a composite FK from each child
   via `RunSQL`, keeping Django's own FK for the ORM. Drift is then impossible, including through
   bulk writes.
3. One shared helper derives `project_id` from the parent; call it from `save()` and every bulk
   path. Do not rely on signals.
4. Retrofit Detection and Classification in stages: nullable column, batched backfill by
   `source_image__project_id`, composite FK added `NOT VALID` then `VALIDATE`, then `NOT NULL`,
   project-leading index `CONCURRENTLY`. `EXPLAIN (ANALYZE)` on the largest local project before
   and after.
5. Cover moves: `Deployment.update_children()` and PR #1192 must also move Detection,
   Classification and the new tables; `ON UPDATE CASCADE` on the composite FK does it in the DB.
6. Detect drift with a new check in the #1188 framework, run after the backfill and periodically.
7. Migration: Django state changes plus raw-SQL constraints, backfill in batches outside one
   transaction, `CONCURRENTLY` index builds on the detection table, no `print()`.
8. Fix `update_children()` fill-if-empty so a wrong non-null project is corrected, not only a
   missing one.

## Measured drift (supervising session, production copy, 2026-10-01)

| Table | Rows | `project` is null | Disagrees with parent |
|---|---|---|---|
| Deployment | 261 | 50 | – |
| Event | 6,978 | 157 | 109 (vs deployment) |
| SourceImage | 15,050,698 | 254,814 | 81,157 (vs deployment); 0 vs event |
| Occurrence | 621,072 | 4,354 | 337 vs deployment; 1,704 vs event |
| Detection → occurrence vs capture | 622,690 | – | 0 |

The fill-if-empty convention has not kept the copies consistent. Why the rows disagree (earlier
moves, edits that bypass `save()`) has not been established. Issue draft:
`../planning/2026-10-01-project-fk-denormalization-ticket-draft.md`.

## Could not verify

Whether Django 5.2 `ForeignKey` can target a `CompositePrimaryKey` model; maintenance status of
django-denorm, FieldTracker, django-lifecycle, and computedfields' limitations and Django 5.x
support; Sentry and Zulip practice; Postgres trigger approaches (no source, untested); what
`fix_missing_relationships.py` repairs; whether production has the same drift as the copy.
