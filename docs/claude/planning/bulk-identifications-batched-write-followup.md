# Batched write path for bulk identifications — follow-up design

**Status**: design only, not built. Follow-up to PR #1371.
**Date**: 2026-07-17

## Verdict

**Do not build this yet.** The v1 loop (one `Identification.save()` per item inside a caught
savepoint) is correct, reuses the only tested determination code, and costs ~8 queries per item on
batches that are bounded by the UI page size (~25–100). A batched rewrite trades that safety for a
saving that does not matter until batches grow past a page.

**The trigger that should force it**: a "select all N occurrences matching this filter" mass-ID
action, or raising `MAX_BULK_IDENTIFICATIONS` (`ami/main/api/serializers.py`) past ~500. At n≈100 the
loop runs ~800 queries in one request; that is acceptable. At n=10 000 it is ~80 000 and holds row
locks for the whole request — not acceptable. The number below is what changes the calculus.

Rough query counts (read from code, **not measured**):

| n | v1 loop | batched | note |
|------|---------|---------|------|
| 25 | ~200 | ~6 | loop fine |
| 100 | ~800 | ~6 | loop fine |
| 1 000 | ~8 000 | ~7 | loop starts to hurt |
| 10 000 | ~80 000 | ~8 | loop unacceptable; batched needed |

Batched cost is roughly constant because every step is a set operation; the loop is linear.

## What the batched path must reproduce

`Identification.save()` (`ami/main/models.py`) does three things per item:

1. Withdraw the user's other non-withdrawn identifications on that occurrence
   (`.filter(occurrence=, user=).exclude(pk=).update(withdrawn=True)`).
2. Insert the row.
3. `update_occurrence_determination(occurrence)` — recompute `determination` and
   `determination_score`.

The **score quirk is the spec**: `update_occurrence_determination` compares an int
(`.values("determination")`) to a Taxon instance, so it always rewrites, and agreeing lifts the score
to 1.0. A batched path must produce the identical result. Do not fix the quirk here (see the separate
ticket below); a change to the score changes which occurrences pass score-threshold filters.

## Algorithm sketch

Order matters: **withdraw before insert**. You cannot exclude pks that do not exist yet, so withdraw
the user's existing identifications on the affected occurrences first, then insert, then recompute.

```python
occ_ids = [item.occurrence_id for item in items]

with transaction.atomic():
    # 1. Withdraw the user's current identifications on these occurrences.
    Identification.objects.filter(occurrence_id__in=occ_ids, user=user, withdrawn=False)\
        .update(withdrawn=True)

    # 2. Insert all new identifications at once.
    created = Identification.objects.bulk_create([Identification(...) for item in items])

    # 3. Recompute determination for every affected occurrence in a few set queries
    #    (see below), then bulk_update the occurrences with update_fields.
```

Step 3, batched. The "best identification per occurrence" is a `DISTINCT ON`:

```sql
SELECT DISTINCT ON (occurrence_id) occurrence_id, id, taxon_id, 1.0 AS score
FROM main_identification
WHERE occurrence_id = ANY(%s) AND withdrawn = false
ORDER BY occurrence_id, created_at DESC, id DESC   -- BEST_IDENTIFICATION_ORDER
```

Every affected occurrence now has at least one non-withdrawn identification (we just inserted one), so
`best_prediction` never has to be consulted for this batch — that removes the one genuinely per-row
query. `bulk_update(occurrences, ["determination_id", "determination_score"])` finishes it. Human
score is always 1.0 (`Identification.score`), so the score column is a constant and needs no join.

If a future batch can also *withdraw* identifications (this one does not), the "every occurrence has a
non-withdrawn identification" assumption breaks and `best_prediction` returns — do not assume it away
without checking.

## Partial-failure reconciliation (the crux)

`bulk_create` is all-or-nothing: it cannot report that row 37 of 200 failed. The v1 contract is
per-row (save the good ones, report the bad). Options:

1. **Validate everything up front, then one atomic batch.** Resolve occurrences/taxa/agree-targets and
   reject any bad item *before* writing, so the only thing that can fail at write time is a concurrent
   delete. Accept that a mid-flight concurrent delete turns into a whole-batch failure (rare). Cleanest
   code; changes the contract from "always partial" to "partial only for pre-write validation errors".
2. **Chunked batches with per-chunk savepoints.** `bulk_create` in chunks of, say, 100; a chunk that
   raises falls back to the v1 per-item loop for that chunk only. Keeps the per-row contract exactly,
   at some complexity. Best if the contract must not change.
3. **Pre-flight existence check then batch, accepting the race.** Simplest, but the race window
   (check → write) makes it the least honest.

**Recommendation: option 2** if the per-row contract is load-bearing for the FE (it is today — the
existing hook reports per-item results), option 1 if the FE is being rewritten anyway and a simpler
"all valid or 400 with per-index errors" contract is acceptable. Decide *with the FE change*, not
separately.

## Divergence risk

Introducing a batched recompute creates a second determination code path next to
`update_occurrence_determination`. They will drift. The honest fix is to **express the scalar function
in terms of the batch function**: `update_occurrence_determination(occurrence)` becomes
`recompute_determinations([occurrence.pk])`, so there is one implementation and the single-item
endpoint exercises the same code the batch does. This should land *before or with* the batched write,
not after.

## The test that must land first

`update_occurrence_determination` has no tests today (`@TODO Add tests` in the source). Before swapping
loop→batched, add a differential/property test that runs both paths over the same fixture matrix and
asserts identical `(determination_id, determination_score, withdrawn flags)`:

Fixture matrix (each row an occurrence state before the new identification):
- agree with the current prediction
- agree with an existing human identification
- brand-new taxon (no prior human ID)
- a prior identification by the **same** user (exercises withdraw-previous)
- a prior identification by a **different** user (must survive)
- an already-withdrawn identification present
- no predictions at all
- an occurrence with no detections
- a duplicate occurrence in the batch (rejected upstream, but assert the recompute is not fed it)

The property: for every state, loop-path result == batched-path result. That test is the gate; without
it the swap is unverifiable.

## Suggested follow-up tickets

### Ticket A — batched write path

> **Title**: Make bulk identifications scale to thousands of occurrences in one request
>
> Today an identifier can submit many identifications in one request, but each is written individually,
> so a very large batch runs a query per occurrence and holds database locks for the whole request.
> That is fine for the page-sized batches the interface sends now, but a future "identify everything
> matching this filter" action would send thousands at once. This replaces the per-item write with a
> set-based one (withdraw, insert, and recompute determinations in a handful of queries regardless of
> batch size), gated behind a differential test that proves the batched recompute matches the existing
> per-item behaviour exactly. Prerequisite: tests for `update_occurrence_determination`, which has none
> today.

### Ticket B — the score-comparison quirk

> **Title**: Decide whether agreeing with a determination should raise its score to 1.0
>
> `update_occurrence_determination` compares a taxon ID to a taxon object, so its "nothing changed"
> branch never runs and every identification rewrites the occurrence's determination score. In practice
> this means agreeing with an existing determination lifts its score from the machine score to 1.0.
> That may be the behaviour we want — a human-confirmed occurrence arguably should score 1.0 — but it
> is currently reached by accident, and the score feeds the default score-threshold filters, so it
> quietly affects which occurrences show up in filtered lists. This ticket is to decide the intended
> behaviour and make the code express it on purpose, with a backfill plan if the decision changes
> existing scores.
