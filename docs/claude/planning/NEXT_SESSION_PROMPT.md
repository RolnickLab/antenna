# Roadmap Distillation - Session Continuation

## First Step

Read `docs/claude/planning/roadmap-distillation-plan.md` — it's the comprehensive living document (~500 lines) with:
- Distilled goals summary ("Trust & Scale", factory QA / conveyor belt analogy, the 5 things that matter most)
- Full strategic context (2026 kickoff themes, field test learnings from Panama, two service tiers, user journeys)
- Prioritization framework (impact tiers, weighting signals, horizon heuristics)
- Phase 1-3 results and methodology
- Phase 4 spec (the remaining work)


claude/planning/roadmap-session-insights.md

## What's Been Done (Phases 1-3)

| Phase | What | Output file |
|-------|------|-------------|
| 1. Categorize CSV | 866 raw items → 862 categorized | `docs/roadmap-categorized.csv` |
| 2. GitHub index & summaries | 954 issues/PRs summarized | `docs/claude/planning/github-summaries.jsonl` + `github-index.md` |
| 3. Dedup & cross-reference | 862 → 754 canonical items, matched to GitHub | `docs/claude/planning/roadmap-deduped.jsonl` |

### Key Phase 3 Numbers
- 420 (55%) untracked — discussed but never ticketed
- 170 (22%) partial — foundation built, needs completion
- 109 (14%) completed
- 55 (7%) tracked — has open issue/PR
- ML/AI has 70 partial items (highest ROI to finish)
- Documentation 98% untracked, Onboarding 100% untracked

## What's Next: Phase 4

**Produce `docs/claude/planning/roadmap-master.csv`** — a sortable spreadsheet for team review.

### Columns
`category, description, mention_count, github_refs, status, status_notes, type, size, proposed_horizon, source_rows`

### How to Generate
1. Read `roadmap-deduped.jsonl` (754 items)
2. Read the prioritization framework from the plan doc (impact tiers, horizon heuristics, strategic overrides)
3. Assign `proposed_horizon` per item using the heuristics
4. Separate completed items into a "done / capability inventory" section
5. Sort by: horizon → category → mention_count (descending)
6. Write as CSV importable to Google Sheets

### Key Prioritization Inputs
- **Factory QA model:** features that help users reach the "conveyor belt phase" (statistical spot-checking, not 100% verification) rank highest
- **Top 5 priorities:** improve presented results + confidence estimation, fix critical bugs, project quick start MVP, new processing pipeline, documentation
- **NOT priorities:** SaaS launch, React migration, fine-grained classification (coarser-but-confident is the new default)
- **Two tiers:** Tier 1 supported partners (feature-complete for their use cases), Tier 2 community/self-hosted (needs great docs)
- **Field test finding:** "high data scenario, we can afford to throw things out" — less wrong > more detailed

### Processing Approach
The 754 items won't fit in one context. Process by category groups (same batches as Phase 3) or by horizon. Use subagents if needed, merge results.

## All Files

| File | Size | Description |
|------|------|-------------|
| `docs/claude/planning/roadmap-distillation-plan.md` | 30K | Living plan doc — READ THIS FIRST |
| `docs/claude/planning/roadmap-deduped.jsonl` | 360K | 754 deduped items (Phase 3 output, Phase 4 input) |
| `docs/claude/planning/github-summaries.jsonl` | 360K | 954 GitHub summaries |
| `docs/claude/planning/github-index.md` | 94K | Full PR + issue title index |
| `docs/roadmap-categorized.csv` | 69K | 862 items categorized (Phase 1 output) |
| `docs/roadmap-batch{1,2,3}.csv` | ~20K each | Raw batch outputs (can delete) |
