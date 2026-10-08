# Code Hygiene in Antenna

Several people and several coding-agent sessions add features to Antenna in parallel, often without
seeing each other's work. This document is for anyone doing a hygiene pass on the backend or the
frontend: before marking a PR ready, after the last piece of a feature lands, or when picking up an
area that several branches have been editing. The short list of questions to ask is in
`.agents/AGENTS.md` under "Code hygiene". This file holds what those questions need to know about
this repository in particular: where the large files are, which existing modules to follow when
splitting them, which way imports should run, where configuration lives, why the test suite is
slow, and the scan commands that work here.

Everything below is a signal to weigh, not a gate. "Noticed, not worth it yet" is a fair outcome for
debt a change ran into. What a branch itself left behind is different: that belongs to the PR that
created it. A follow-up ticket is for debt the work found but did not cause, or for a cleanup too
large to review alongside the change.

Figures carry the date and commit they were measured at. Re-run the commands in the last section
before acting on any of them; they start going stale on the next merge.

## The established practice behind each question

The lines in `.agents/AGENTS.md` are well-trodden ground elsewhere. Naming the source keeps the
checklist short and settles arguments faster than re-deriving the reasoning.

| Question | Known as |
|---|---|
| Does a fact or helper now live in two places? | **DRY** (Hunt and Thomas, *The Pragmatic Programmer*), applied at the **rule of three** (Fowler, *Refactoring*). DRY is about duplicated knowledge, not duplicated text: two blocks that read alike but encode different decisions are coincidental duplication and stay apart |
| Is this abstraction premature? | **AHA**, avoid hasty abstractions; "duplication is far cheaper than the wrong abstraction" (Sandi Metz); **YAGNI** |
| Is the same concept called the same thing everywhere? | One word per concept (*Clean Code*); a rename that follows a change of meaning is part of the change |
| Are string keys and `if`-chains multiplying? | Fowler's *primitive obsession* and *switch statements* smells; replace them with an enum or a small registry |
| Has a file stopped having one subject? | **Single responsibility principle**; the *large class* and *divergent change* smells; separation of concerns |
| Is there already a home for this? | **Principle of least astonishment**; follow the conventions already in the codebase |
| Is this PR mixing a refactor with a behaviour change? | Fowler's **two hats**: wear one at a time, ideally in separate commits or PRs |
| Is it safe to delete this? | **Chesterton's fence**: find out why it is there first |
| Should I tidy this while I am here? | The **boy scout rule** (Martin), opportunistic and preparatory refactoring (Fowler, Beck), without gold-plating the PR |
| Dead code and stale comments | **Broken windows** (Hunt and Thomas); comment rot |
| Is the newest feature taking over a shared surface? | Don't let newest win: **recency bias** in design. A feature is one note in the chord; it slots into the existing order, default off or collapsed. Related to the **open/closed principle** (extend without reshaping what already serves others) |
| Is a failure being swallowed? | **Fail fast**: an empty handler turns a bug into "nothing happens" |
| Are the tests still earning their place? | Beck's **test desiderata** (fast, isolated, deterministic); **DAMP over DRY** inside tests; one reason to fail per test; mock what you own |
| Deferred cleanup | **Technical debt** (Cunningham): fine when named and tracked, expensive when silent |

## Hotspots

Measured on `main` at `38a512ea` on 2026-10-08. "Commits" counts commits on `main` that touched the
file in the previous six months; `main` is squash-merged, so this is roughly the number of PRs.
Migrations are excluded.

| File | Lines | Classes | Functions and methods | Commits (6 months) |
|---|---:|---:|---:|---:|
| `ami/main/tests.py` | 8,692 | 69 | 542 | 32 |
| `ami/main/models.py` | 5,484 | 43 | 263 | 24 |
| `ami/main/api/views.py` | 2,709 | 47 | 102 | 29 |
| `ami/ml/tests.py` | 2,330 | 12 | 104 | 11 |
| `ami/main/api/serializers.py` | 2,101 | 81 | 43 | 18 |
| `ami/jobs/tests/test_jobs.py` | 1,836 | 12 | 99 | 9 |
| `ami/jobs/tests/test_tasks.py` | 1,764 | 9 | 75 | 7 |
| `ami/jobs/tasks.py` | 1,491 | 1 | 31 | 14 |
| `ami/jobs/models.py` | 1,444 | 17 | 52 | 11 |
| `ami/ml/models/pipeline.py` | 1,370 | 5 | 25 | 6 |
| `ui/src/utils/language.ts` | 845 | | | 18 |

The four largest `ami/main` files are also the four most-edited Python files. That combination is
what makes merges collide and lets a third copy of something hide in a file that already contains
two. In these files the usual advice to extend the existing module is often the wrong answer, because
adding to them hides the addition; new modules and subpackages are welcome. On the frontend,
`ui/src/utils/language.ts` is the string table and its length follows its role, and no component
file is over 420 lines.

## Where new code goes

When `ami/main` needs a new module, follow one of the arrangements the repository already uses
rather than inventing another:

| Precedent | What it shows |
|---|---|
| `ami/ml/models/` | A `models/` package with one module per model, in place of a single `models.py` |
| `ami/ml/orchestration/` | Workflow and dispatch logic kept off the models, with its own `tests/` package beside it |
| `ami/ml/post_processing/` | A pluggable family: a base class (`base.py`), one module per task, a registry keyed by each task's `key` (`registry.py`), an `admin/` subpackage, and tests that mirror the modules |
| `ami/main/models_future/` | Querysets, filters and aggregate queries extracted from `ami/main/models.py`, one module per subject |
| `ami/jobs/tests/` | A `tests/` package split by subject in place of one `tests.py` |
| `ami/ml/schemas.py` | The contract with external processing services, kept free of Antenna-side concepts such as projects and users |

A good proposal names the module after the domain concept it owns rather than the mechanism it
uses, draws the line where another person would draw it, and keeps the new module's imports running
in the direction described below so that it does not join a cycle. The move itself reads best as its
own PR: pure relocation, no behaviour change. A split that only shifts lines without making a
boundary clearer is worth skipping.

## Which way imports run

The target is that `ami.main` models and querysets form the domain core and do not import `ami.ml`
or `ami.jobs`; `ami.ml` builds on `ami.main`, and `ami.jobs` builds on both. The shared layers,
`ami.base` and `ami.utils`, import none of the apps. The admin and API modules of `ami.main` are a
presentation layer and may import from any app.

Measured on `main` at `38a512ea` on 2026-10-08 with the import-linter contracts in the last section,
the code does not meet that target yet. These are the existing exceptions, listed so that new code
does not add to them:

- `ami/main/models.py` imports `ami.ml` four times: `ami.ml.schemas.BoundingBox` at module level
  (line 46), `Pipeline` and `ProcessingService` for type checking (line 54), and two imports inside
  functions (lines 376 and 2121). It imports `ami.jobs.models.Job` for type checking (line 53) and
  inside a function (line 315).
- `ami.base` and `ami.utils` import `ami.main.models`: `ami/base/permissions.py`, `ami/base/views.py`
  and `ami/utils/requests.py` at module level or for type checking, and `ami/base/models.py` inside
  functions.
- `ami.ml` and `ami.jobs` import each other. Eight non-test `ami.ml` modules import
  `ami.jobs.models`: at module level in `ami/ml/orchestration/jobs.py`,
  `ami/ml/orchestration/processing.py` and `ami/ml/post_processing/admin/actions.py`, and for type
  checking or inside functions elsewhere. Seven `ami.jobs` modules import `ami.ml`. Which of the two
  should depend on the other has not been decided, so a PR that adds an edge in either direction
  should say so in its description.

Moving an import inside a function stops Python from failing on the cycle, but the two modules are
still coupled. Treat a function-level import as a marker of a boundary in the wrong place, not as a
fix.

## Where configuration lives

A value that another deployment might need to change, such as a sender address, a host, a bucket, a
timeout or a size limit, belongs in `config/settings/`, read from the environment with a default that
works for a fresh checkout. Someone running Antenna from this repository should never have to edit
code to change it. `config/settings/base.py` reads the environment through `django-environ`, and its
existing settings are the pattern to copy:

```python
DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="Antenna <noreply@example.com>")
NATS_TASK_TTR = env.int("NATS_TASK_TTR", default=300)
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int("DJANGO_DATA_UPLOAD_MAX_MEMORY_MB", default=100) * 1024 * 1024
```

A new variable also goes into the example environment files, `.envs/.local/.django` and
`.envs/.production/.django-example` (or `ui/.env.example` for the frontend), so that it can be found
without reading the settings module.

Code reads the setting and does not declare a second default, because a fallback in the reader
drifts from the one in settings. For example, `ami/ml/orchestration/nats_queue.py:49` reads
`getattr(settings, "NATS_TASK_TTR", 30)` while the settings default is 300: the two disagree by a
factor of ten, and the reader's value is never used. Values that are product constants rather than
deployment choices stay in code, in the module that owns the concept.

## Test cost

The backend CI workflow has become about four times slower in a year without covering four times as
much. Successful runs of `test.backend.yml` took a median of 4.5 minutes in September 2025 (50 runs)
and 18.9 minutes in October 2026 (76 runs), measured with `gh run list` on 2026-10-08. Between July
and October 2026, while the runtime was climbing, the number of tests on `main` grew only from 627 to
760 (measured 2026-10-06), and a grep finds 779 test functions today. The growth is in the cost of
each test, not in their number. Issue #1481 tracks bringing it back down.

The measured causes, largest first (profiled with `pytest --durations=0` on 2026-10-06):

1. **Fixtures built for every test instead of once per class.** There are 103 `setUp` methods
   against 10 `setUpTestData` (recounted 2026-10-08). The shared helper `setup_test_project()` costs
   about 0.64 s per call, because creating a test project also creates a processing service, which
   makes an HTTP status call and registers pipelines. `create_captures()` costs about 0.42 s. Called
   from `setUp`, that cost repeats for every test in the class.
2. **`TransactionTestCase` without `available_apps`.** All eight such classes are in
   `ami/jobs/tests/test_tasks.py`, and none sets `available_apps`, so every teardown flushes the
   database and re-runs `post_migrate`, including permission, content-type and role creation for
   every project. That costs roughly 4 to 6 s per test. Re-measured on 2026-10-08, the 40 tests in
   that module took 146 s, and its eight slowest tests (3.8 to 5.4 s each) all belong to
   `TransactionTestCase` classes.
3. **Real network calls with retry backoff.** Two single tests took 24 s and 12 s waiting on
   retries.

What to do in new and edited tests:

- Build shared data in `setUpTestData`. The classes in `ami/ml/post_processing/tests/` and
  `ami/ml/tests.py:1460` are examples to copy.
- Use `TestCase`. Reach for `TransactionTestCase` only when a test needs committed transactions,
  and then set `available_apps` and say why in the class docstring.
- Patch the transport for anything that would leave the process. A test that needs a processing
  service should get a stub, not a live endpoint.
- Before adding a test, check whether another test already proves the same thing at the same layer.
  Before merging, sort the tests a PR adds into those that prove something new, those that repeat
  another test, and those whose name claims more than the body checks; cut the second kind and
  rewrite the third. Readable repetition inside a test is fine; a test that proves nothing new is
  not.
- Single-row fixtures cannot catch N+1 queries, so query-count tests need several rows (see the
  checklist in `.agents/AGENTS.md`).

## Swallowed failures

Measured on `main` at `38a512ea` on 2026-10-08 with the commands in the last section: ruff finds one
`try`/`except`/`pass` and one `try`/`except`/`continue` without logging, a grep finds six more
`except SomeError: pass` blocks, and there are 44 broad `except Exception` handlers outside
migrations. Not all of these are wrong, since some catch an exception that genuinely means "nothing
to do". Each one should either surface the error (log it, record it on the job, re-raise) or carry
a one-line comment saying why ignoring it is safe. A failed save or delete that is silently ignored
looks to the user like a button that does nothing, and takes far longer to diagnose than an error
would. The same applies on the frontend to an empty `catch` or an `onError` that does not tell the
user anything.

## Settled conventions

- Public or underscore-prefixed: if another file would call it, give it a public name on the model
  that owns the concept; if not, keep the leading underscore.
- Class names are nouns qualified by their domain, not verbs.
- UI vocabulary follows what users call things rather than what the model is called. Occurrences
  and detections are the nouns.
- A new foreign key in the admin uses `raw_id_fields` or `autocomplete_fields`, so that the change
  form does not render every row of a large table.
- An index on a large table is added with `AddIndexConcurrently` in a non-atomic migration of its
  own (for example `ami/main/migrations/0097_detection_and_classification_job_indexes.py`).
- Comments state the rule and the one reason, and link out for the long version: see "Writing
  Comments, Docstrings, and PR Text" in `.agents/AGENTS.md`, and `ui/AGENTS.md` for the leaner
  frontend norm. Write them against `main`, not against an earlier round of the same PR.
- Helpers and patterns to reuse before writing new ones are in
  `docs/claude/reference/canonical-patterns.md`.

## Scan commands

Each command below was run from the repository root on 2026-10-08 against `main` at `38a512ea`, and
the note under it says what it reported then. None of them changes a file. `uvx` runs a Python tool
without installing it into the project, and `npx` does the same for Node tools. The repository lints
Python with flake8 and has no ruff, vulture, radon or import-linter configuration, so these commands
pass their options on the command line.

**Largest files and churn.**

```bash
git ls-files -z '*.py' | xargs -0 wc -l | grep -v ' total$' | grep -v migrations | sort -n | tail -12
git ls-files -z 'ui/src/*.ts' 'ui/src/*.tsx' | xargs -0 wc -l | grep -v ' total$' | sort -n | tail -6
git log --format= --name-only --since=6.months origin/main | grep -v '^$' | grep -v migrations \
  | sort | uniq -c | sort -rn | head -15
```

These produced the hotspot table above. The `grep -v ' total$'` matters: on a large tree `xargs`
splits the list across several `wc` calls, and each prints a `total` line that would otherwise sort
to the top.

**Slowest tests.**

```bash
docker compose run --rm django pytest --ds=config.settings.test --durations=25 -q
docker compose run --rm django pytest ami/jobs/tests/test_tasks.py --ds=config.settings.test --durations=8 -q
```

The full run takes about fifteen minutes locally. The second command profiles one module; it
reported 40 tests in 146 s, with the slowest eight all in `TransactionTestCase` classes. pytest
counts a unittest `setUp` inside the "call" phase, so per-test fixture cost shows up in each test's
own time rather than as setup.

**Complexity.**

```bash
uvx ruff check ami config --isolated --select C901 --config 'lint.mccabe.max-complexity=15' \
  --exclude '**/migrations/**'
uvx radon cc -s -n D ami config -e '*/migrations/*'
```

Ruff reported seven functions above complexity 15, among them `filter_processed_images` in
`ami/ml/models/pipeline.py`, `Deployment.sync_captures`, and the taxa import and update management
commands. Radon also counts boolean operators; it grades 49 functions C or worse, and its D-or-worse
list adds `save_results` and `process_images` in `pipeline.py`, `MLJob.process_images`,
`process_nats_pipeline_result` and `model_agreement_for_project`. `uvx radon mi -s ami` scores
`ami/main/models.py`, `ami/main/tests.py` and `ami/main/api/views.py` at 0, which mostly reflects
their length.

**Long parameter lists and swallowed failures.**

```bash
uvx ruff check ami config --isolated --select PLR0913 --exclude '**/migrations/**' --statistics
uvx ruff check ami config --isolated --select S110,S112,BLE001 --exclude '**/migrations/**' --statistics
grep -rnE '^\s*except[^:]*:\s*$' -A1 ami --include='*.py' | grep -E '^\S+-[0-9]+-\s+pass\s*$' | grep -v migrations
```

These reported 28 functions with more than five arguments, and the swallowed-failure counts given
above (one S110, one S112, 44 BLE001, and six further `except ...: pass` blocks).

**Dead code.**

```bash
uvx vulture ami config --min-confidence 80 --exclude '*/migrations/*'
```

This reported ten findings. Most are parameters that a signature requires but the body does not use,
such as `__exit__` arguments and test-loader hooks. One is a real unreachable `return` in
`ami/base/serializers.py:97`. Below 80 % confidence the output is dominated by Django and DRF names
that are used by reflection, so read those findings rather than acting on them.

**Duplicated blocks.**

```bash
npx --yes jscpd@4 --min-lines 10 --reporters console --format python --ignore '**/migrations/**' ami config
npx --yes jscpd@4 --min-lines 10 --reporters console --format typescript,tsx ui/src
```

For Python this reported 13 clones covering 161 lines (0.7 %), concentrated in `ami/main/charts.py`
and in the two taxa management commands. For TypeScript it reported 69 clones covering 1,363 lines
(3.0 %). A clone is a prompt to read, not to merge: check whether the two copies encode the same
decision before extracting them.

**Import direction.**

```bash
cat > /tmp/antenna-importlinter.ini <<'EOF'
[importlinter]
root_package = ami

[importlinter:contract:core]
name = ami.main models do not import ami.ml or ami.jobs
type = forbidden
source_modules =
    ami.main.models
    ami.main.models_future
forbidden_modules =
    ami.ml
    ami.jobs

[importlinter:contract:ml-jobs]
name = ami.ml does not import ami.jobs
type = forbidden
source_modules =
    ami.ml
forbidden_modules =
    ami.jobs
EOF
uvx --from import-linter lint-imports --config /tmp/antenna-importlinter.ini
```

This reported both contracts broken, with the import chains summarised under "Which way imports
run". It follows imports inside functions and type-checking blocks as well; add
`exclude_type_checking_imports = True` under `[importlinter]` to leave out the latter. The contracts
are not committed, so this is a measurement rather than a CI check.

**Frontend lint.** `cd ui && yarn lint` runs the repository's pinned ESLint configuration, which is
the same check the pre-commit hooks use.
