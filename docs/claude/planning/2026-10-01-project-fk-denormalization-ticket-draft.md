# Keep a project column on every project-scoped model and enforce it in the database

## Summary

Many Antenna models carry their own copy of the `project` foreign key instead of reaching the project through a chain of parents. The copy makes permission checks, list pages, counts and data moves cheap, and several planned tables (embeddings, algorithm runs and results, measurements) will want it from their first migration. Today the copy is filled by convention and nothing in the database checks it. On a copy of the production database we measured rows where it is empty or disagrees with the parent. If this work is done, a project column can be trusted everywhere it exists, new tables get it by a single agreed pattern, and project-scoped queries on the largest tables stop depending on total table size.

## Why a copied project column matters

1. **Permission filtering.** Visibility of draft projects is applied through a per-model `project_accessor` path. A direct column keeps that filter to one join or none.
2. **List endpoints.** Without a project filter, list queries appear to scan whole tables. PR #1133 proposes requiring `project_id`, which only helps if the column is cheap to filter on.
3. **Composite indexes.** The existing indexes on captures and occurrences lead with project. That is only possible where the column exists.
4. **Project-scoped counts.** Detection has no project column. Based on `EXPLAIN (ANALYZE)` on a local production copy (measured 2026-09-02), a project-scoped detection count sequentially scans the whole detection table for large, medium and small projects alike, at roughly 1.8 s, 0.6 s and 0.5 s. Classification queries scoped by project show the same shape.
5. **Moving data between projects.** PR #1192 moves deployments and their children. A copied column has to be updated in every child, and the database could do part of that itself.
6. **Project deletion and retention.** Deleting or archiving a project is simpler when every row can be selected by its own column. This is based on reasoning, not measurement.
7. **Future tables.** Detection and capture embeddings, algorithm runs and results, and occurrence measurements all need project-filtered queries, including similarity search restricted to one project. The model outputs design note covers these tables.
8. **External precedent.** Multi-tenant systems such as Citus carry the tenant column on every table and in its keys so related rows stay together. Antenna's project is the same kind of boundary.

## What exists today

Based on code reading, these models carry their own `project` foreign key: Deployment, Event, SourceImage and Occurrence in `ami/main/models.py`. Detection and Classification reach it through `project_accessor` paths, which are used only for permission filtering. Nothing in the database requires the copy to match its parent.

- SourceImage and Event fill `project` from the deployment inside `update_calculated_fields()`, only when it is empty. SourceImage imports from storage call this explicitly before `bulk_create`, so bulk safety depends on that caller.
- Occurrence gets its project at creation, in the detection's occurrence-creation method and in the pipeline results saver.
- `Deployment.update_children()` runs from `Deployment.save()` and updates Event, Occurrence and SourceImage rows that disagree. It skips signals, does not touch other models, and the background-task version is commented out.
- Django's `bulk_create`, `bulk_update` and `QuerySet.update()` skip `save()` and signals, so any rule living in `save()` or a signal is bypassed on those paths.

## Measured drift (production database copy, 2026-10-01)

Measured:

| Table | Rows | `project` is null | Disagrees with parent |
|---|---|---|---|
| Deployment | 261 | 50 | – |
| Event | 6,978 | 157 | 109 (vs deployment) |
| SourceImage | 15,050,698 | 254,814 | 81,157 (vs deployment); 0 vs event |
| Occurrence | 621,072 | 4,354 | 337 vs deployment; 1,704 vs event |
| Detection → occurrence vs capture | 622,690 | – | 0 |

The fill-if-empty convention has not kept the copies consistent. A wrong non-null value is never corrected unless the deployment is saved again. We have not yet established why the rows disagree, for example whether they come from earlier moves or from edits that bypass `save()`.

## Directions to discuss, ordered by effort and risk

| Option | What it does | Trade-offs |
|---|---|---|
| (a) Periodic check and repair | Add a project-mismatch check to the data-integrity command framework in PR #1188, dry-run by default | Lowest risk and shows the real scale of drift. Detects after the fact and prevents nothing. |
| (b) One shared derive helper | A single function sets `project` from the parent, called from `save()` and every bulk path | Removes the "caller must remember" problem. Still relies on discipline, and `QuerySet.update()` can bypass it. |
| (c) Database enforcement | `UNIQUE (id, project_id)` on the parent and a composite foreign key `(parent_id, project_id) REFERENCES parent (id, project_id)` with `ON UPDATE CASCADE`, added with `RunSQL` beside Django's own foreign key | Makes a mismatch impossible, including on bulk paths, and moves children on a parent change. Costs an extra check per write and a more careful migration. Django has no composite foreign key field, so the constraint lives outside the model definition. |
| (d) Retrofit Detection and Classification | Nullable column, batched backfill, constraint added `NOT VALID` then validated, then `NOT NULL`, then a project-leading index built `CONCURRENTLY` | Addresses the full-table scan. Largest effort and the highest migration risk on the biggest tables. |

We would start with (a) together with (b). The first shows how bad drift is in production and gives a repair path, which any later constraint needs anyway, and the second is small and low risk. We would apply (c) first to new tables, where there is nothing to repair, then decide on (d) once the repair and the measurements are in.

## What we still need to verify

- The repair of the existing null and mismatched rows, before any `NOT NULL` or composite foreign key can be added.
- Whether Django's ORM tolerates the extra composite constraint on bulk paths.
- The write cost of the additional foreign key check.
- `EXPLAIN (ANALYZE)` before and after on the largest project for Detection counts.
- Whether production has the same drift as the copy.
- What the `fix_missing_relationships` management command repairs.
- Whether Django 5.2 composite primary keys change any of this. We could not confirm from the documentation.

## Related

- PR #1133: require `project_id` on list endpoints to prevent full table scans.
- PR #1188: data-integrity check framework.
- PR #1192: command to move a project's data between projects.
- The detection-count sequential scan finding above (measured 2026-09-02).
- The model outputs design note.

Scrub check: no hostnames, customer or deployment names, local filesystem paths, or project ids appear in this draft.
