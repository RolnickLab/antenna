# Meeting Board Cards — Redo with Strategic Grounding

## Problem with Previous Attempt

Phase 4 (roadmap-master.csv with horizons) is done and good. But when we created **meeting board cards** from those 754 items, the subagents clustered bottom-up by item descriptions without deeply understanding the strategic context. Result:
- Many underlying items were misunderstood or misattributed
- Bloated catch-all cards (one had 47 items including field protocol notes like "label SD cards with tape")
- Themes drifted from the carefully distilled analysis in the plan doc
- User stories were generated from surface-level item text, not from actual understanding of the platform

The themes, goals, and prioritization in `docs/claude/planning/roadmap-distillation-plan.md` are correct. The card generation needs to be **top-down from those themes**, not bottom-up from raw items.

## First Step

Read these two documents carefully — they are the source of truth:

1. **`docs/claude/planning/roadmap-distillation-plan.md`** (~500 lines) — the living plan doc with:
   - "Trust & Scale" theme, factory QA / conveyor belt analogy
   - The 5 things that matter most (improve results + confidence, fix bugs, quick start, new pipeline, docs)
   - Field test learnings from Panama ("less wrong > more detailed", 7 concrete techniques)
   - Impact tiers (10 levels), horizon heuristics, weighting signals
   - Two service tiers, two user journeys, key personas
   - Phase 3 insights (55% untracked, ML/AI highest ROI to finish, docs strategic gap)

2. **`docs/claude/planning/roadmap-session-insights.md`** — additional context from earlier sessions

Also available:
- `docs/claude/planning/roadmap-master.csv` — 754 items with horizons assigned (Phase 4 output)
- `docs/claude/planning/roadmap-deduped.jsonl` — 754 items with full metadata
- `docs/claude/planning/meeting-board-cards.md` — the previous attempt (reference for format, not content)

## What to Produce

**`docs/claude/planning/meeting-board-cards.md`** — overwrite the existing file.

~35-40 themed cards for a FigJam planning meeting. Two interactive activities:
1. **Partner prioritization** — which partners to commit to for complete case studies (needs upper management input)
2. **Feature prioritization** — move cards between now / maybe / never columns

### Card Format

Each card needs:
- **Title**: Plain language, 5-8 words, no jargon
- **One-liner**: What this means for users, one sentence
- **User stories**: 2-3 per card, "As a ___, I want ___ so that ___" — ready as detail cards during discussion
- **Effort**: S / M / L / XL for the cluster
- **Item count**: How many underlying roadmap items
- **Status summary**: What exists vs. what's needed
- **Underlying items**: Listed for reference (collapsible)

Also produce **`docs/claude/planning/meeting-board-cards.csv`** for FigJam/Sheets import.

### Approach: Top-Down from Themes, Not Bottom-Up from Items

**DO NOT** cluster by reading item descriptions and grouping similar ones. Instead:

1. **Define card themes from the plan doc's strategic analysis.** The plan already identifies the key themes:
   - The 7 "improving presented results" techniques (tracking, class masking, rank predictions, confidence estimation, bad data removal, good defaults, improved detector)
   - Verification intelligence (statistical, not exhaustive)
   - Processing reliability & the new pipeline
   - Data upload & import workflows
   - Project quick start / onboarding
   - Species list management (regional lists, class masking setup)
   - Auth & permission fixes (password reset, signup, roles)
   - Documentation (the 98% untracked strategic gap)
   - Export for partners (Darwin Core 8x mentioned)
   - Analytics & transparency (accuracy metrics, phenology)
   - Adjacent use cases (non-time-series, pollinators)
   - Community & ecosystem integration
   - etc.

2. **Map items TO themes**, not themes FROM items. Read each item and ask "which strategic theme does this serve?" Some items won't fit cleanly — that's fine, put them in the closest theme or a small "other" bucket.

3. **Write user stories from platform understanding**, not from item text. The personas are:
   - **Field ecologist** — deploys cameras, reviews data, exports for analysis
   - **Taxonomist** — verifies species IDs, manages taxa lists
   - **ML researcher** — develops/deploys models, evaluates accuracy
   - **Project manager** — organizes teams, tracks progress
   - **New user** — first time trying the platform

   The plan doc describes their journeys. Use that, not just the item description.

### Target Card Distribution

- **now-3mo**: ~12-15 cards (93 items) — these need the most detail since they're actionable
- **next-6mo**: ~12-15 cards (304 items) — moderate detail
- **later/someday**: ~8-10 cards (248 items) — coarser grouping is fine
- **done**: summary only (109 items) — reference, not on the board

### Processing Approach

The 754 items + plan doc won't fit in one context window. Recommended approach:

1. **Main agent**: Read the plan doc, define all ~35-40 card themes with titles, one-liners, and user stories. Write these to a JSON file.
2. **Subagents** (parallel, by horizon): Each reads the card themes + its horizon's items from roadmap-master.csv, maps items to themes, counts, collects GitHub refs and status info.
3. **Main agent**: Merge subagent results into card themes, write final markdown + CSV.

This ensures themes come from strategic understanding (main agent with plan doc) while item mapping is parallelized.

### Quality Checks

- No card should have >25 items (if it does, it should be split)
- Every user story should make sense to someone who has never seen the codebase
- Some items are field protocol or meeting action items, not software features — skip or note as out-of-scope. Examples: "Label each SD card with tape", "Fresh SD cards", "Sync the SD cards every day to hardware", "Michael to assist with X for new paper", "Find intern and train on basic tasks". But be careful: items that *look* like brainstorm notes may actually contain valuable detail about how to approach a feature (e.g., "How to score confidence (hardness to identify visually, how many similar species...)" is a useful spec for the confidence estimation card, not a throwaway note). Similarly, model retraining items ("Retrain the model for Totumas data", "Re-training panama model with fewer", "Training new regional models") are actionable work — a Panama/Central America model retrain is planned for next month. These belong under ML pipeline / improving results cards.
- The "improving presented results" cluster from the plan doc should map to ~3-4 separate cards (it's the #1 priority and has 7 distinct techniques)
- Documentation should NOT be one giant card — split by audience (user guide vs. self-install vs. developer docs)

## Meeting Context

The audience is diverse: ecologists, ML researchers, project managers, and upper management. They need to:
- Understand what each card means without technical background
- React to proposed priorities and move cards around
- Decide which partners to commit to (affects what "now" means)
- NOT break down tasks — that happens after the meeting for whatever lands in "now"

The meeting will use FigJam with sticky notes / cards that participants can drag between columns (now / maybe / never / already done).
