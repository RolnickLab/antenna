# Code Hygiene in Antenna

The general checklist — look for duplication, spaghetti, files that lost their subject, tests that
no longer earn their place, comments written against the branch instead of `main` — lives in the
agent's global instructions under "Code Hygiene: Look for Opportunities". This file is the
Antenna-specific layer: the measurements, the precedents to follow, and the smells this repo has
actually paid for.

## Where the big files are (measured 2026-10-08)

| File | Lines |
|---|---|
| `ami/main/tests.py` | 7,654 |
| `ami/main/models.py` | 5,236 |
| `ami/main/api/views.py` | 2,512 |
| `ami/ml/tests.py` | 2,290 |
| `ami/main/api/serializers.py` | 2,006 |

In `ami/main` the usual advice to extend the existing module is often wrong: these files are large
enough that adding to them hides the addition. New modules and subpackages are wanted here. What
matters is the boundary — name the module after the domain concept it owns, keep its imports running
one way so it stays a leaf, and follow one of the arrangements the repo already uses rather than
inventing a sixth:

- `ami/ml/models/` — a `models/` package instead of one `models.py`
- `ami/ml/orchestration/` — workflow and dispatch logic off the models
- `ami/ml/results/` — Antenna-side schemas and writers, kept separate from `ami/ml/schemas.py`,
  which is the external processing-service contract
- `ami/main/models_future/` — querysets and filters extracted from `ami/main/models.py`
- `ami/jobs/tests/` — tests split into a package mirroring the code

A relocation reads best as its own PR: pure moves, no behaviour change. A split that shuffles lines
without making the boundary clearer is worth skipping.

## Test suite and CI (measured 2026-10-06, ticket #1481)

The backend CI workflow went from a 4.4 minute median (Sep 2025) to 19.5 minutes (Oct 2026), of
which the Django test step is 10.9 minutes. Test count on `main` only grew from 627 to 760 over the
same period, so **per-test cost is the whole story**, in this order of size:

1. **Fixtures built per test.** 108 classes use `setUp`, 8 use `setUpTestData`. `setup_test_project()`
   costs 0.64 s per call (it creates a processing service, which makes a real HTTP status call and
   registers pipelines) and `create_captures()` 0.42 s. Build fixtures once per class; keep the
   processing service out unless a test needs it.
2. **`TransactionTestCase` without `available_apps`.** Every teardown flush re-fires `post_migrate`
   — permissions, content types and role creation for all projects — at roughly 4–6 s per test. All
   eight such classes are in `ami/jobs/tests/test_tasks.py`. Use the plain `TestCase` unless a test
   genuinely needs committed transactions, and set `available_apps` when it does.
3. **Real network calls with retries.** Two single tests cost 24 s and 12 s waiting on retry
   backoff. Patch the transport.

Conversions already in the tree to copy: `680ffd32`, `e989d46b`, `9fdffb25`, `9d545d36`, `30cc9b7a`
(fixtures once per class) and `d92db94a` (pruning a test matrix).

## Smells this repo has paid for, and their fixes

From the review rounds on #1461 (post-processing results) and its neighbours. The pattern on the
left is the thing to look for; the right-hand column is what it became.

| Smell | Fix |
|---|---|
| One stored value parsed in several places (job `params["config"]` read by a history builder, a serializer, a label map) | One parser driven by the task's config schema, shared by all readers |
| The same list defined twice (a `Kind` enum beside a schema dict beside a UI list) | The model carries its kind; the registry is built from one mapping |
| A side table per type (per-type label maps, formatters, special cases) | Metadata on the schema field itself, and one lookup table |
| An overloaded field (`score` meaning a prediction score in one row and a result value in another) | One meaning per field; nested sections instead of a catch-all `payload` |
| Stored data that can be derived (`original_taxon_id`, `original_score`) | Derived from the relation that already records it |
| A fallback that guesses around missing data (taking a project from an occurrence's station) | Raise or skip with a warning; track the data problem |
| Verb or generic class names (`BatchResults`, `ResultData`) | Nouns qualified by their domain (`AlgorithmResultWriter`, `AlgorithmResultData`) |
| A helper duplicated between a component and its child (`getRefLabel`) | One exported helper |
| A reader that assumes the current writer's shape | Tolerant reads plus a guard test: an unregistered kind or an old JSON shape must not 500 |
| Inconsistent locking between two writers of the same rows | Both `select_for_update()` in pk order |
| An extension point with no guard test | A test that fails when a new type is unmapped |
| A new FK rendering a `<select>` of every row in the admin | `raw_id_fields` or `autocomplete_fields` |
| A new job-written table invisible to `?job=` | An `EXISTS` branch in `OccurrenceQuerySet.created_or_updated_by_job()` |
| An index built inside `ALTER TABLE` on a large table | `db_index=False` plus `AddIndexConcurrently` in its own `atomic = False` migration (`main/0097`, `main/0099`) |

## Local conventions that already settle naming questions

- Public versus underscore-prefixed: would another file want to call it? Yes → public name, on the
  model that owns the concept. No → leading underscore, stays local.
- Class names are nouns qualified by their domain, not verbs.
- UI vocabulary follows what users call things, not what the model is called — occurrences and
  detections are the nouns; tracking is the verb.
- Comment length and the "link out instead of explaining inline" rule: `.agents/AGENTS.md` →
  "Writing Comments, Docstrings, and PR Text", and `ui/AGENTS.md` → "Comments" for the leaner
  frontend norm.
- Helpers and patterns to reuse before writing new ones: `docs/claude/reference/canonical-patterns.md`.
