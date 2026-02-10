# Roadmap Distillation: Non-Obvious Insights & Discussion Notes

Captured from the Feb 2026 session. These are nuances that emerged from conversation and might get lost.

## Strategic Insights

### Partner projects drive the dev schedule, not the other way around
"Use these [partner projects] to guide the development schedule" — this means the roadmap isn't a fixed plan. It's a menu of options that gets sequenced based on what specific partners need next. The partner meetings ARE the sprint planning input.

### Many CSV items assume the wrong direction
The 866 items were collected over 2 years when the implicit assumption was "more detail = better." The team's recent strategic shift to "coarser-but-confident by default" means a large chunk of feature requests (finer classification, more species, detailed labels) need to be reframed. They're not wrong, they're just lower priority than getting the coarse results trustworthy first. Probably 50+ ML/AI items are affected by this reframing.

### The product is a system that helps you stop needing to verify
This came up in discussion and is the sharpest way to describe the conveyor belt model. Antenna isn't a verification tool — it's a calibration tool. Every feature should be moving users toward the moment they say "good enough, let it run." Features that assume 100% manual verification don't scale and shouldn't be prioritized.

### Documentation is the *entire product* for Tier 2
Not just "nice to have." Under the two-tier model, Tier 2 (community/self-hosted) users interact with Antenna primarily through documentation. If the docs don't exist, Tier 2 doesn't exist. The 98% untracked rate in Documentation is a strategic problem, not a backlog gap.

### Mention count = demand across stakeholders, not just repetition
The CSV aggregated items from 12+ different planning docs (working group meetings, kickoffs, field notes, presentations). When something is mentioned 5x or 8x, that means 5-8 *different groups* or *different contexts* raised it. It's a proxy for cross-stakeholder demand, not just one person repeating themselves.

### The "turn on processing" timing question is unresolved
"Do we turn processing back on before or after the results are better? (or coarser?)" — this is a chicken-and-egg question that affects everything. Partners need results to give feedback, but showing bad results erodes trust. The coarser-results-by-default approach may be the answer: turn it on, but only show what you're confident about.

### AI-assisted development changes the size calculus
T-shirt sizes (S/M/L/XL) were assigned to every item but the team noted these matter less now. A large feature that closes a critical workflow gap is more valuable than ten small polish items, and with agentic development, the implementation cost of "large" items has dropped. Prioritize by impact, not effort.

## Process Insights (for future distillation runs)

### Subagent batching patterns that worked well
- **Phase 1 (categorize):** 3 batches of ~290 rows, purely parallel, merge with head/tail
- **Phase 2 (summarize GitHub):** 6 batches split by type + time period (open PRs, open issues, closed issues, merged PRs by 3 time windows), all parallel
- **Phase 3 (dedup):** 4 batches by category groups, each getting both CSV items AND GitHub summaries for its categories. This was the most complex — agents needed to do semantic matching, not just keyword matching
- Validate every JSONL output with a Python script before merging

### The 70% similarity threshold for dedup was about right
Reduced 862 → 754 (12.5% dedup). More aggressive would lose nuance, less aggressive would leave obvious duplicates. The most-duplicated item (Darwin Core export, 8x) was correctly identified.

### Abandoned PRs (167) were correctly skipped
They add noise without signal — if a PR was closed without merge, the work either went into a different PR or was abandoned. No value in summarizing them.

### Some items span multiple categories
The dedup agents were told "don't merge across categories" which is correct for the spreadsheet output, but some items genuinely span categories (e.g., "confidence estimation" is both ML/AI and UI/UX). The Phase 4 output should note this where relevant.

## Open Questions for Team Discussion

1. Which specific partner projects will anchor the 3mo schedule?
2. What's the MVP for "project quick start"? Single form? Or just auto-process after manual upload?
3. How to handle the 420 untracked items — bulk-create GitHub issues? Or just use the spreadsheet as the source of truth?
4. Sprint cadence: 3 weeks dev + 1 week docs/planning — has this been adopted?
5. Kanban vs sprints — which fits the "stay flexible" goal better?
6. Planning for multiple apps — what does this mean concretely? Separate processing service apps? Different frontends?
7. What's the SLA for the Tier 2 community environment?
