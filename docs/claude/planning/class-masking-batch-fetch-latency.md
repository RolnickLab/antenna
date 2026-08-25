# Class masking: batched scope reads (branch `fix/class-masking-batch-fetch-latency`)

Follow-up to #1376. Prod job 2834 (project 86, Ogden St.) was still revoked as stalled on
2026-07-27 with `classifications_checked: 0`, despite #1376 having shipped.

## What #1376 fixed, and what it missed

#1376's mechanisms all fired in production. From the job log:

| time | event |
|---|---|
| 00:57:55 | job starts, post-processing stage marked `STARTED` |
| 00:57:57 | scope `.count()` returns 70,279 in 2s (was 208s with `.distinct()`) |
| 00:58:10 | category map expanded, `on_setup` posts `classifications_total: 70279` |
| 01:15:00 | REVOKED — "no progress for 16.8 min", `classifications_checked: 0` |

The stall is *inside the row loop*, before the first `batch_size` flush.

## Root cause

`QuerySet.iterator(chunk_size=N)` bounds memory, not latency. Time-to-first-row scales with
the size of the whole scope. Measured on the local prod-copy DB, `Classification` rows for
algorithm 11 (29,176 classes, `logits` and `scores` ~140 kB each):

| scope rows | time to first row |
|---|---|
| 200 | 4.65 s |
| 500 | 11.07 s |
| 1,000 | 22.06 s |
| 2,798 | 61.09 s |

~22 ms/row, unchanged by `chunk_size`. `Job.STALLED_JOBS_MAX_MINUTES` is 10, so a scope of
this width cannot reach its first heartbeat before the reaper revokes it.

Probable mechanism is Django declaring a `WITH HOLD` cursor in autocommit
(`django/db/backends/postgresql/base.py`: `withhold=self.connection.autocommit`), which
Postgres materialises at commit. **Not isolated** — re-running inside `transaction.atomic()`
(`WITHOUT HOLD`) still took 55–56 s over three runs. The size-scaling is measured; the
mechanism is inferred.

This is consistent with the job history: 3,643 rows (07-06) and 11,906 rows (07-02) both
cleared first-row inside the cutoff and succeeded; every run at 42k+ has been revoked, and
the 07-17 attempt died with `signal 9 (SIGKILL)`. The one run that does not fit is 07-09 at
4,393 rows, which was revoked; that remains unexplained.

## Why EXPLAIN did not catch it

`EXPLAIN (ANALYZE)` executes the plan but never returns rows to the client, so it never
detoasts a large array column, never puts it on the wire, and never parses it in Python. The
plan for the 2,798-row scope reports **23 ms** against a real fetch of **61 s**.

Related asymmetry, and why #1376 landed where it did: `Sort` over a TOASTed column is cheap
because it sorts pointers (`width=141`), whereas `DISTINCT` compares values and therefore
detoasts. Removing `.distinct()` fixed the `COUNT` and left the row loop untouched.

Written up in `docs/claude/reference/query-patterns.md` under the query anti-patterns.

## The change

Resolve the scope to a list of ids once, then read it one `batch_size` piece at a time:

```python
scope_ids = list(classifications.order_by().values_list("pk", flat=True))
for start in range(0, total, batch_size):
    batch = list(
        classifications.filter(pk__in=scope_ids[start : start + batch_size])
        .order_by()
        .defer("scores")
        .select_related("detection", "detection__occurrence")
    )
```

- `defer("scores")` — the loop never reads `scores`, and it is as large as `logits`.
- `select_related` — `classification.detection` and `detection.occurrence` are read per masked
  row and were two queries each.
- `total` now comes from `len(scope_ids)` rather than a separate `.count()`. That removes the
  disagreement behind the 07-06 log line "Re-scored 3912 of 3643 classifications", where the
  count and the iteration saw different row sets.

Measured on a 2,798-row scope: first batch **3.22 s** (was 61.58 s); **91 rows/s** end to end
(prod was achieving ~3.5 rows/s).

## Deliberately not in this change

Fetch throughput is 260–430 rows/s locally, but prod's successful 07-02 run managed ~4.3
rows/s after first-row latency is subtracted, so the run is **write-bound**. This branch stops
the reaping; it does not make a 70k-row run fast. Ranked follow-ups:

1. **Stop writing `scores` and a copied `logits` on each masked row.** Measured 140 kB +
   105 kB per new row — ~17 GB for a 70k run. `scores` is derivable from `logits` plus the
   mask; `logits` is reachable through `applied_to`. Touches stored semantics.
2. **Batch the occurrence determination updates.** The flush does one
   `occurrence.save(update_determination=True)` per occurrence — ~8.4k individual saves on the
   07-02 run.
3. **Scope filter on determination (mihow's proposal, supersedes part of #1377).** Masking only
   zeroes excluded classes, so if a classification's argmax taxon is already in the taxa list it
   is a kept class and cannot be dethroned — the determination is unchanged by construction.
   `.exclude(taxon_id__in=<taxa in list>)` is therefore a safe prefilter on an indexed column,
   and skipped rows never have their logits fetched. Two caveats: #1377 measured only
   948/3,814 = 24.9% of masked rows repeating the source taxon on serbia, so this is roughly a
   quarter fewer rows rather than an order of magnitude; and it assumes `taxon_id` equals
   `index_to_taxon[argmax(logits)]`, which held 100/100 on a local sample but is unverified at
   scale.

Pushing the mask into SQL was measured and rejected: subscripting a TOASTed array
(`logits[i]`) appears to re-detoast the whole value per subscript, so extracting 1,168 of
29,176 indices ran at 290 ms/row — ~123x slower than fetching the array whole, and two
attempts hit the 30 s `statement_timeout`.

## Tests

- `test_progress_is_reported_before_the_whole_scope_is_read` — the reaper-facing invariant: a
  progress report reaches the job after reading at most `batch_size` of 6 rows.
- `test_scope_does_not_fetch_the_unused_scores_column`
- `test_detection_is_not_queried_once_per_row`

A fourth test asserting "no single query materialises the whole scope" was written and then
cut: the progress test pins the same property behaviourally, and the SQL matcher also caught
the determination-recomputation queries, making it fail for the wrong reason.
