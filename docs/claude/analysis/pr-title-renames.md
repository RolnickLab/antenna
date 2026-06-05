# PR title renames — empirical sweep (2026-06-04)

Analysis of every PR title that `mihow` renamed after creation, on `RolnickLab/antenna`. Purpose: measure how often Claude-drafted, implementation-jargon titles got hand-corrected to plain user-effect titles, to ground the PR-title writing rules in real data rather than anecdote.

- **Raw data:** [`pr-title-renames.tsv`](./pr-title-renames.tsv) — columns: `PR`, `actor`, `ISO-date`, `from`, `to`. 80 rows.
- **Method:** GitHub records title changes as `renamed` timeline events. Swept all `mihow`-authored PRs (state=all):
  ```bash
  gh api repos/RolnickLab/antenna/issues/N/events --paginate \
    --jq '.[] | select(.event=="renamed") | {actor:.actor.login, from:.rename.from, to:.rename.to, at:.created_at}'
  ```
  (Issues and PRs share the events endpoint.) Scope: `mihow` PRs only; cross-author renames not swept.

## Headline numbers

- **80 rename events** across **57 distinct PRs**, all by `mihow`. Range **2024-08-12 → 2026-06-05**.
- **~21 mechanism → effect** corrections (the pattern of interest): `from` = Conventional-Commit prefix / module path / code names / jargon; `to` = plain user-facing effect.
- **~6 scope-broadened**: narrow example title → names the framework/pattern (#1289 ×2, #1301, #1197, #1104, #634, #992).
- **~53 minor/other**: `[Draft]`/`[Do Not Merge]`/`(redo)` status tags, typos, punctuation, casing, mechanism→mechanism rewords.

## Findings that shaped the rules

1. **Effect-first is the stable long-run voice, not a new preference.** The instinct predates caveman mode — early renames are raw branch-name → effect:
   - #688 `Fix/celery workers` → **Fix background tasks from disappearing**
   - #759 `Feat/faster taxa backend` → **Fix taxa pages**
   - #909 `Feat/quickstart prototype auto process` → **Auto-process manually uploaded images (if enabled)**
   The `fix(jobs):` Conventional-Commit style is a caveman-era overlay on top of a consistent effect-first preference.

2. **Real-time oscillation under pressure.** #1307 and #1301 were renamed effect → mechanism → effect before settling. The pull toward mechanism is under-pressure noise, not a real preference. Default: when unsure, effect.

3. **Three drift sources to kill**, all seen in the data: Conventional-Commit prefix (`fix(jobs):`), jargon/mechanism (`emit storage URL direct from serializer when cache is warm`), and **branch-name auto-titles** (`gh pr create` pre-fills from the branch slug — `Feat/taxa-covers` shipped as a title several times). Never accept the branch-name auto-title.

## Clearest mechanism → effect examples

| PR | from (drafted) | to (renamed) |
|----|----------------|--------------|
| 1331 | `perf(thumbnails): emit storage URL direct from serializer when cache is warm` | Option for thumbnails: store and serve full URLs instead of hitting server |
| 1300 | `perf(api): rewrite collection counts as subqueries; trim capture list SELECT` | Speed up the captures list view |
| 1301 | `Denormalize SourceImageCollection counts as cached columns` | Speed up the capture set list view |
| 1292 | `feat(projects): wire session_time_gap_seconds into event grouping` | Allow users to customize the time gap between sessions |
| 1289 | `feat(post-processing): admin scaffolding precursor (pydantic schema, form base, parameterized template)` | Framework for admins to trigger and review post-processing methods |
| 1234 | `fix(jobs): ack NATS after results-stage SREM; defer task_failure for in-flight async jobs` | fix(jobs): prevent jobs from hanging in STARTED state with no progress |
| 1311 | `fix(newrelic): make app_name env-var-driven (drop from ini)` | fix(monitoring): allow distinguishing data from different deployments in New Relic |

## Related

- The rules these findings feed: user memory `feedback-pr-title-voice` and `feedback-pr-desc-voice`, and the "PR titles & summaries" subsection of the global writing-style guidance.
- Worked example PR: #1289 (title + `## Summary` + `### List of Changes` all rewritten effect-first this session).
