# Roadmap Distillation Plan

> **Living document.** Reusable process for turning scattered planning docs into a prioritized, GitHub-aligned roadmap. Run this quarterly or whenever planning docs accumulate.

## How to Reuse This Process

**When to run:** After a planning cycle, retreat, or when feature requests from multiple sources need consolidation.

**Prerequisites:**
- Aggregated CSV of feature/bug/idea items (one `primary_description` column minimum)
- Access to the GitHub repo via `gh` CLI
- Claude Code with subagent support

**Process overview:**
1. Categorize raw items against the standard category scheme (Phase 1)
2. Fetch and summarize all GitHub issues/PRs (Phase 2)
3. Deduplicate items and cross-reference with GitHub (Phase 3)
4. Produce a sortable spreadsheet for team review (Phase 4)

**Incremental updates:** If you already have `github-summaries.jsonl`, only fetch new issues/PRs since the last run date and append. Re-run Phase 3-4 against the updated data.

---

## Distilled Goals Summary

What 866 feature requests, 954 GitHub entries, team kickoff notes, and field testing boil down to:

### The Core Bet for 2026: "Trust & Scale"

Antenna works as a prototype. The question is whether ecologists will *rely* on it.

**The factory QA analogy:** When a factory sets up a new production line, QA is intensive — inspecting every widget, calibrating machines, finding systematic errors. But the goal was never to inspect every widget forever. The goal is to *characterize the error rate well enough* that you can turn on the conveyor belt and spot-check a percentage for ongoing calibration. You know the line produces ~10% imperfect widgets, you know *which kinds* of imperfections to watch for, and that's good enough to ship.

**Antenna's version of this:**
1. **Calibration phase** (per project/region/camera) — intensive verification, measuring where the model is good and bad, tuning thresholds, building trust in the specific setup
2. **Conveyor belt phase** — the system runs, results flow, users spot-check a statistical sample for ongoing calibration rather than verifying every occurrence
3. **The transition** — the moment a user says "I trust this enough to let it run." Antenna's job is to *make that transition possible* by providing the metrics, transparency, and defaults that let users know when they've reached it.

This means every feature should be evaluated through this lens: does it help users *reach the conveyor belt phase faster*, or does it help them *stay calibrated once they're there*? Features that assume 100% manual verification don't scale. Features that help characterize and communicate error rates do.

Trust requires:
- **Honest confidence** — show what's reliable, admit what's not, never present a bad prediction confidently
- **Measurable error characterization** — "the model is X% accurate on species Y in your region with your camera" not just a global accuracy number
- **Statistical verification tools** — suggest which occurrences to verify for maximum calibration value, not just "verify everything"
- **Complete workflows** — partners can go from raw images to publishable data without dev team intervention
- **Reliability** — the tool doesn't lose work, jobs don't hang, basic things (like password reset) work

### The 5 Things That Matter Most Right Now

1. **Improve presented results + confidence estimation** (field-validated, ~7 techniques) — tracking, class masking, rank rollups, confidence estimation, bad data removal, good defaults. This is the single highest-impact cluster. The goal: help each partner project reach the "conveyor belt" phase where they trust the output enough to stop verifying every occurrence and switch to statistical spot-checking.
2. **Fix critical bugs & reliability issues** — processing service API, milestone #27, password reset (5x mentioned), dangling jobs. These erode trust independent of result quality.
3. **Project quick start MVP** — "Does this work on my data?" Single form → auto-create project → process → results. Let new users see immediately how good (or bad) the system is on their data — the first step of calibration.
4. **New processing pipeline running** with partner testing and feedback loops. Each partner project is a calibration cycle that both improves the system and builds a case study.
5. **Documentation** — 98% of doc items are untracked. Without docs, Tier 2 (self-hosted community) can't set up their own calibration → conveyor belt cycle.

### What's NOT a priority in 2026
- Not launching SaaS (general availability is for planning, not public signup)
- Not React 19 / framework migration (no partner is blocked by this)
- Not fine-grained classification (coarser-but-confident is the new default)
- Not new research features before existing ones are solid

### Concepts That Emerged from Field Testing (not in any planning doc)
- **Confidence estimation** using class priors + species-level accuracy + temperature scaling
- **Verification intelligence** — which occurrences are most helpful to verify? Most valuable for retraining?
- **Immediate UI updates from verified results** without retraining (pseudo-labels / overrides)
- **"High data, throw things out"** philosophy — we can afford to discard uncertain results

---

## Objective

Distill feature/bug/idea items from team planning docs into a prioritized roadmap with 3mo, 6mo, 12mo, and beyond horizons. Cross-reference with GitHub issues, PRs, and milestones.

**Current run:** Jan 2026 — 866 items from `docs/aggregated_features_list-jan2026.csv` (12+ planning docs, 2 years of meetings).

## Source Data Inventory

| Source | Count | Notes |
|--------|------:|-------|
| CSV feature items | 866 | From 12+ planning docs across 2 years |
| Open GitHub issues | 189 | |
| Closed GitHub issues | 233 | |
| Total PRs | 699 | 488 merged, 44 open, 167 abandoned |
| Milestones | 9 | All open, some overdue |

## Platform Understanding

See `CLAUDE.md` for full architecture, module details, database schema, and dev commands.
See `docs/antenna_abstract_and_presentation.md` for platform vision and presentation script.

**Purpose:** Bridge ecology and AI — let non-ML-experts run computer vision on camera trap data at scale, collaboratively. Open-source orchestrator between people (ecologists, ML researchers, taxonomists, decision-makers) and technologies (cameras, storage, ML models).

**North star:** Users should trust Antenna data the way they trust weather data.

### Key User Personas

1. **Field ecologists** — deploy cameras, review data, export for analysis
2. **Taxonomists/entomologists** — verify species IDs, manage taxa lists, annotate
3. **ML researchers** — develop/deploy models, evaluate accuracy, improve pipelines
4. **Project managers** — organize teams, track progress, configure projects
5. **Conservation decision-makers** — consume insights, dashboards, reports

### Two User Journeys

- **Sandbox/demo** (self-service NOW): frictionless try-before-you-buy. Quick start, demo project, upload, process, see results. Conference follow-up funnel.
- **Enterprise/institutional** (whiteglove NOW, self-service LATER): paying clients get hands-on onboarding — custom taxonomy, regional models, hardware integration. Self-service features for enterprise (project config, pipeline mgmt, member management) come after their monitoring programs are running reliably day-to-day.

**Constraint:** Not launching SaaS in 2026. General availability is a planning horizon, not a public launch. Focus is on supported partners + a self-hostable community version with great docs.

### Categorization Scheme

Standard categories used across all phases. Maps to codebase modules:

| Category | Codebase modules / areas |
|----------|-------------------------|
| Data-Management | `ami.main` (SourceImage, Event, Deployment), image import, session grouping, storage |
| ML/AI | `ami.ml` (Pipeline, Algorithm, ProcessingService), detection, classification, post-processing |
| UI/UX | `ui/src/pages/`, verification, annotation, gallery, dashboards |
| Taxonomy | `ami.main` (Taxon, TaxaList), species lists, hierarchy |
| Export/Interop | `ami.exports`, Darwin Core, GBIF, CSV, API clients |
| Analytics/Viz | Charts, phenology, abundance, co-occurrence views |
| Permissions/Auth | `ami.users`, django-guardian, roles, teams, object-level permissions |
| Infrastructure | Celery, NATS (PSv2), Docker, cloud deployment, scaling |
| Onboarding | Self-service flows, quick start, demo projects |
| Documentation | User docs, tooltips, developer guides |
| DevEx | Testing, CI/CD, code quality, developer experience |
| Research | Exploratory, academic, partnerships |
| Community | Collaboration, outreach, open science |

### GitHub Milestones (as of Feb 2026)

| Milestone | Open | Closed | Notes |
|-----------|------|--------|-------|
| Self-service improvements | 43 | 14 | Core priority: streamlined UX, demo without guidance |
| Cleanup, technical debt | 59 | 10 | Non-urgent catch-all |
| ML features | 14 | 1 | General ML milestone |
| High-priority issues | 7 | 6 | Active fires |
| Up for revision | 12 | 2 | Needs triage |
| Post Panama feature integration | 3 | 0 | Overdue (Sep 2025) |
| Canadian Forest Pest Pipeline | 1 | 5 | Mostly done |
| Platform Documentation | 1 | 1 | Overdue (Dec 2025) |
| Processing & data infra | 3 | 0 | External tooling |

### Active Work Areas (as of Feb 2026)

- Processing Service v2 (NATS-based async processing) — multiple open issues/PRs
- Permissions & roles refactor — model-level permissions framework in progress
- Configurable taxa lists — API refactored, frontend in progress
- UI improvements — date pickers, layout tweaks, filter display
- UI framework assessment — Remix migration proposal open

### Strategic Goals (from Feb 2026 team notes)

Three pillars, not just features:

**1. General Availability (planning horizon, not SaaS in 2026)**
- Sandbox environment (multiple options being evaluated)
- Coarser / less fine-grained results by default (reduce noise, build trust)
- New processing service running and tested
- Documentation (user guide, self-install guide, one-click deploy options like Digital Ocean)

**2. Capacity Building**
- Tech debt & infrastructure automation
- Project management improvements
- Expanding to adjacent use cases (non-time-series: lab scopes, drawers; pollinators/general detection)

**3. Solid Case Studies**
- Commit to several projects end-to-end (partner relationships, regular meetings)
- Collaboration on the analysis side with ecologists
- These prove the platform works and generate word-of-mouth

### Feature Priorities (from Feb 2026 team notes)

**New processing pipeline:**
- Make it available, have partners test it for feedback
- Open question: turn processing back on before or after results improve? (or go coarser?)

**Better results (the core value proposition):**
- Better detector, tracking, filters, class masking
- Order-level classifier with calibration
- Rank rollups with calibration
- Coarser results as default (less wrong > more detailed)

**Transparency about results (builds trust — impact tier 2):**
- Auto-generated: "The model is X% accurate on your data"
- Manual messages: "This model works on these images in this region"
- Showing mAP score as user edits

**Extended annotation features:**
- Bbox editing & multiple detection models
- Clustering support

**Documentation (the 98% untracked gap):**
- User guide
- Self-install guide
- One-click install options (Digital Ocean etc.)

**Adjacent use cases:**
- Non-time-series data (lab microscopes, specimen drawers)
- Pollinators / general insect detection (not just moths)

---

## 2026 Strategic Context

### Overarching Theme: "Trust & Scale"

Create a strong offering, but stay ready to pivot. Solidify the core, keep the edges fluid.

### Three Strategic Goals

1. **Trust building** — measuring uncertainty, providing confidence to scale. Help users know what to trust and what to improve. "When do you let the conveyor belt run?"
2. **Quality building** — improve accuracy, stability, and quality of what already exists before adding new things. Foundation of code, infrastructure & UI should work really well and let us expand & maintain.
3. **Capacity building** — tech debt, infrastructure automation, documentation, preparing for change (AI speed, cameras, the world, research questions).

### Two Service Tiers

**Tier 1: Supported partners (full support, few projects)**
- Complete case studies with full dev team support
- Formal agreement with each partner
- Regularly scheduled meetings per project
- Use these projects to guide the development schedule
- Goal: "feature complete" for these specific use cases

**Tier 2: Community / self-hosted (minimal support)**
- Lightly managed environment with community support
- Great documentation about self-hosting Antenna
- Defined SLA expectations
- This is the sandbox / "everyone else" tier

### Development Themes (from 2026 kickoff)

1. **Measuring uncertainty, providing confidence to scale** — metrics in UI, aggregates tab, "when do you let the conveyor belt run?"
2. **Amplifying current research utility** — features & fixes for what's already most accurate (species richness, biomass). Showcase results of current data/processes. Use current features for other applications.
3. **Quality improvement of what we have** — accuracy, stability, documentation. Not new features — better existing ones.
4. **Preparing for change** — AI speed, new cameras, evolving research questions. Planning for multiple apps? Keep clear purpose but handle different usage categories.

### Field Test Learnings (Mount Totumas, Panama)

Real-world observations from an end-to-end test with ecologists. These should heavily influence now-3mo priorities.

**Key insight: "High data scenario — we can afford to throw things out."**
Don't squeeze the orange for small accuracy improvements. Instead, be confident about what you present and honest about what you don't know. Less wrong > more detailed.

**The confidence problem:**
- Some predictions are really good
- Some predictions are not good, but the system *thinks* they are good
- How can we better estimate and present what we're confident about vs not?

**Improving presented results (concrete techniques):**

| Technique | What it does | Status |
|-----------|-------------|--------|
| **Tracking** | Use multiple detections to improve species prediction of an occurrence | Partial (PR work exists) |
| **Class masking** | Remove species that don't occur in the region, rerank scores | Tracked (4x mentioned in CSV) |
| **Rank predictions** | Never present low-confidence result, roll up ranks until confident (→ "Not identifiable") | Partial (order-level classifier exists) |
| **Estimate confidence** | Use class priors, species-level accuracy, temperature scaling | Untracked (new) |
| **Remove bad data** | Too small, too blurry, cut-off → "Not identifiable" | Partial (quality filters exist) |
| **Good defaults** | Hide irrelevant classes (not-a-moth), confidence thresholds from algorithms + project settings | Partially tracked |
| **Improved detector** | Reduce overlaps in high-data scenarios, skip non-insect artifacts, more camera types | Tracked |

**Verification intelligence (statistical, not exhaustive):**
The goal is NOT "verify every occurrence." The goal is to help users calibrate — understand their error rate, improve it where it matters, and reach the point where they trust the conveyor belt. Verification is a calibration tool, not a bottleneck.
- Which occurrences are most informative to verify? (active learning / maximum calibration value)
- Which are most valuable for retraining? (highest impact on error rate)
- Can verified results immediately update UI without retraining? (pseudo-labels / overrides)
- At what point has the user verified enough to trust the output? (calibration threshold)

**Priorities identified for summer & fall 2026:**

1. **Fix critical issues** — processing service API, milestone #27 items
2. **Improve presented results** — filtering, good defaults, post-processing (issues exist but need milestone/tags)
3. **Project quick start** — "Does this work on my data?" flow. Start with images → auto-create draft project, stations, sites, process. What's the MVP? Single form? ASAP version = use current manual upload but auto-process.
4. **Data upload tool** — start with CLI version in ami-camera-utils
5. **Diagrams & documentation** — explain the vision, document workflows per user type
6. **Sprint cadence** — 3 weeks dev, 1 week documentation & planning

### Organizational Questions (in progress)

- How to track communication with external contacts?
- Individual & collective goals?
- Better observability for non-devs & intermittent participants?
- Stay on course but flexible? Kanban instead of sprints?
- Which parts solidify, which stay fluid?
- Sprint cadence: 3 weeks dev, 1 week documentation & planning (proposed)

## Prioritization Framework

### Primary Lens: Feature-Complete for Partner Case Studies

The sharpest prioritization question: **"Does this feature unblock a partner project from going end-to-end?"** If yes, it's now-3mo. If it improves quality of existing features, next-6mo. If it's new capability, later.

### Impact Tiers (highest to lowest)

Every feature evaluated through: *does it help users reach the conveyor belt phase, or stay calibrated once there?*

1. **Calibration → conveyor belt transition** — confidence estimation, error characterization per project/region/camera, statistical verification suggestions, coarser-but-honest defaults. The core unlock.
2. **Complete workflows end-to-end** — if a partner can't finish their study without dev intervention, that's a blocker. Processing, verification, export must all work without hand-holding.
3. **Reliability & stability** — bugs, dangling jobs, error handling. The tool must not lose work or silently fail. Trust killers.
4. **Improving presented results** — tracking, class masking, rank rollups, bad data removal, good defaults. These make the conveyor belt output *better* so users reach confidence faster.
5. **Scale** — handle real-world data volumes (500K+ images per project). Processing v2, async pipelines, performance. The conveyor belt needs to actually run fast.
6. **Collaboration** — roles, permissions, multi-user verification, team workflows. Multiple people calibrating together > one person alone.
7. **Ecosystem integration** — Darwin Core, GBIF, iNaturalist, ML training export. Data needs to flow in and out of the conveyor belt.
8. **Analytics & insight** — phenology, abundance, co-occurrence, biomass. The "so what?" — the ecological questions the conveyor belt output can answer.
9. **Documentation & self-hosting** — user guide, self-install guide, one-click deploy. Critical for Tier 2 users to set up their own conveyor belt.
10. **Polish & DX** — UI consistency, developer experience. Important but not blocking adoption.

### Sorting Heuristic for Proposed Horizons

**now-3mo** (Trust & partner case studies):
- Blocks a partner from going end-to-end → now
- Bugs, reliability, dangling jobs → now (milestone #27 critical issues)
- **Improve presented results** → now (the #1 field finding: filtering, good defaults, rank rollups, class masking, remove bad data)
- **Confidence estimation & transparency** → now (core 2026 theme, field-validated need)
- New processing pipeline running + partner testing → now
- Coarser results by default → now
- **Project quick start MVP** → now (sandbox funnel: "does this work on my data?")
- Impact tier 1-3 items → bias toward now

**next-6mo** (Quality of what we have):
- Improve accuracy/quality of existing features → next
- Extended annotation, better detector, tracking → next
- Impact tier 4-5 + high mention_count → next
- Documentation (user guide, self-install, one-click deploy) → next (Tier 2 enabler)
- Amplify current research utility (species richness, biomass) → next

**later-12mo** (Expand & prepare):
- Adjacent use cases (non-time-series, pollinators) → later
- Ecosystem integration (GBIF, iNaturalist) → later unless partner needs it sooner
- Impact tier 6-7 → later
- Infrastructure for multi-app / multiple usage categories → later

**someday** (Stay ready to pivot):
- Research items, exploratory ML → someday
- Community/organizational process items → someday (important but not code)
- Polish, DX items not blocking anything → someday

**done** (Capability inventory):
- Already completed → separate section documenting what's been built

### Weighting Signals

| Signal | Weight | Why |
|--------|--------|-----|
| Mention count (across planning docs) | High | Repeated demand = real need |
| GitHub activity (open PR/issue, recent discussion) | High | Momentum, someone already cares |
| Impact tier (see above) | High | Does it close a workflow gap? |
| Status (partial > tracked > untracked) | Medium | Partial work = lower marginal cost to finish |
| Type (bug > feature > improvement > research) | Medium | Bugs block adoption |
| Size (t-shirt) | Low | Less relevant with AI-assisted development |

---

## Phase Plan

### Phase 1: Categorize the CSV — DONE

Processed 866 items in 3 parallel batches → merged into `docs/roadmap-categorized.csv` (862 clean rows).

**Output columns:** `row_num, description, category, size, type`

**Distribution:**
- Top categories: UI/UX (181), ML/AI (143), Infrastructure (92), Data-Management (90), Documentation (61)
- Top sizes: M (345), S (194), L (178), XS (81), XL (64)
- Top types: feature (447), improvement (157), research (98), documentation (77), bug (63)

**How to reproduce:** Split CSV into ~300-row batches. Each subagent reads its batch + the category scheme, outputs `row_num, description, category, size, type`. Merge with `head -1 batch1.csv > merged.csv && tail -n +2 batch*.csv >> merged.csv`.

### Phase 2: Summarize & Index GitHub — DONE

**Index file:** `docs/claude/planning/github-index.md` — all 699 PR titles + 422 issue titles with dates/states. 955 marked [S]ummarized, 168 unsummarized (abandoned PRs).

**Merged summaries:** `docs/claude/planning/github-summaries.jsonl` (360K, 954 entries)
- 532 PRs (44 open + 96 last 6mo + 193 last 18mo + 199 older)
- 422 issues (189 open + 233 closed)
- Each entry: `{number, title, state, date, summary, categories[], codebase_areas[]}`
- 167 abandoned (closed-not-merged) PRs skipped

**How to reproduce:** Fetch via `gh issue list` / `gh pr list` with `--json number,title,state,body,...`. Split by time period. Each subagent reads its batch JSON, writes JSONL summaries. Merge with `cat`. Update index with `[S]` markers via regex.

### Phase 3: Deduplicate & Cross-Reference — DONE

**Result: 862 raw items → 754 canonical items** (12.5% dedup rate)

Merged output: `docs/claude/planning/roadmap-deduped.jsonl`

Split by category groups into 4 parallel batches:

| Batch | Categories | CSV in | GH in | Canonical out |
|-------|-----------|-------:|------:|--------------:|
| A | UI/UX, Analytics/Viz, Onboarding | 244 | 591 | 215 |
| B | ML/AI, Research | 171 | 349 | 153 |
| C | Data-Management, Infrastructure, DevEx | 208 | 738 | 186 |
| D | Taxonomy, Export/Interop, Permissions/Auth, Documentation, Community | 240 | 414 | 200 |

**Output fields per item:**
`description, category, size, type, duplicate_count, source_rows[], github_matches[], status, status_notes`

#### Status Breakdown

| Status | Count | % | Meaning |
|--------|------:|--:|---------|
| untracked | 420 | 55% | Not in GitHub — discussed but never ticketed |
| partial | 170 | 22% | Foundation built, needs completion |
| completed | 109 | 14% | Done |
| tracked | 55 | 7% | Has open issue/PR |

#### Status by Category

| Category | Total | Completed | Partial | Tracked | Untracked |
|----------|------:|----------:|--------:|--------:|----------:|
| UI/UX | 155 | 49 (31%) | — | 11 (7%) | 95 (61%) |
| ML/AI | 125 | 12 (10%) | 70 (56%) | 13 (10%) | 30 (24%) |
| Infrastructure | 83 | 14 (17%) | 34 (41%) | 6 (7%) | 29 (35%) |
| Data-Management | 79 | 10 (13%) | 39 (49%) | 2 (3%) | 28 (35%) |
| Documentation | 49 | — | — | 1 (2%) | 48 (98%) |
| Community | 49 | — | — | — | 49 (100%) |
| Taxonomy | 41 | 2 (5%) | 9 (22%) | 11 (27%) | 19 (46%) |
| Analytics/Viz | 37 | 9 (24%) | — | — | 28 (76%) |
| Permissions/Auth | 31 | 7 (23%) | 4 (13%) | 1 (3%) | 19 (61%) |
| Export/Interop | 30 | 2 (7%) | 1 (3%) | 5 (17%) | 22 (73%) |
| Research | 28 | 3 (11%) | 8 (29%) | 3 (11%) | 14 (50%) |
| DevEx | 24 | 1 (4%) | 5 (21%) | 2 (8%) | 16 (67%) |
| Onboarding | 23 | — | — | — | 23 (100%) |

#### Most-Mentioned Items (demand signal)

| Mentions | Category | Description |
|---------:|----------|-------------|
| 8x | Export/Interop | Darwin Core export and ML retraining export formats |
| 5x | Permissions/Auth | Password reset when not logged in |
| 5x | ML/AI | Generalized pipeline — general insect detector & global moth classifier |
| 4x | Data-Management | Reworking collections — dynamic filters & datasets |
| 4x | ML/AI | Restrict to species list (class masking) |
| 4x | UI/UX | Interlinking between occurrence and session detail views |
| 4x | Permissions/Auth | Configure project members (partially implemented) |
| 3x | Documentation | Research & document plan for easier data import from cameras |
| 3x | Infrastructure | Processing stability / stabilization |
| 3x | ML/AI | Order-level classifier with calibration & size estimation |
| 3x | Infrastructure | Optimization & hardening (image resizing etc.) |
| 3x | Documentation | Configuration docs for processing services, pipelines |
| 3x | Data-Management | Import data processed externally (detections/predictions) |

#### Key Insights from Phase 3

**The gap between discussion and action:**
55% of items discussed across 12+ planning docs over 2 years have never been ticketed in GitHub. This is the biggest structural finding — demand exists but isn't being captured as trackable work.

**ML/AI is the highest-ROI category to finish:**
70 items are "partial" — the foundations are built (pipelines, processing services, detection models), but completion work remains. Finishing these has lower marginal cost than starting new work, and directly enables the "Trust & Scale" theme.

**Documentation is a strategic gap, not a nice-to-have:**
48 of 49 documentation items are untracked. Under the two-tier service model, documentation is the *entire product* for Tier 2 (community/self-hosted) users. Without it, there is no Tier 2.

**Onboarding has zero GitHub presence:**
23 items, all untracked. This means the sandbox/demo experience — the top of the funnel for new users and conference follow-ups — has had no formal development attention.

**The "transparency about results" theme is underrepresented:**
Only 3-4 CSV items touch uncertainty/accuracy reporting, yet it's a core 2026 strategic theme ("when do you let the conveyor belt run?"). This needs to be elevated beyond what mention counts alone would suggest.

**Coarser results by default is a product strategy shift:**
Not well-represented in the CSV (which mostly asks for *more* detail). The team's recent decision to default to confident-but-coarser results inverts the assumption of many feature requests. Items asking for finer classification need to be re-evaluated in light of this.

**Password reset bug (5x mentioned) is a trust killer:**
A basic auth flow that doesn't work makes the platform feel unreliable regardless of how good the ML pipeline is. Trivial to fix, high signal.

**How to reproduce:** Prep data by extracting CSV items and GH summaries per category group into JSON files. Each subagent gets its group's data, deduplicates with ~70% semantic similarity threshold, cross-references by title/summary similarity.

### Phase 4: Produce Sortable Roadmap Spreadsheet — DONE

**Output:** `docs/claude/planning/roadmap-master.csv` — importable to Google Sheets / Notion

**Columns:**
1. `category` — natural grouping
2. `description` — canonical item description
3. `mention_count` — times referenced across planning docs (demand signal)
4. `github_refs` — linked issue/PR numbers with states
5. `status` — completed / partial / tracked / untracked
6. `status_notes` — 1-sentence context on what's done vs remaining
7. `type` — feature / bug / improvement / research / documentation / design
8. `size` — t-shirt size (background field)
9. `proposed_horizon` — AI-suggested: now-3mo / next-6mo / later-12mo / someday
10. `source_rows` — row numbers from original CSV for traceability

**Completed items** go to a separate section/sheet — they document what's been built and serve as a "capability inventory."

Final prioritization is a team conversation — this spreadsheet is the input to that conversation.

**Phase 4 Results (Feb 2026):**

Processed 754 items in 4 parallel batches by category group, applying the prioritization framework heuristics.

| Horizon | Count | % | Description |
|---------|------:|--:|-------------|
| now-3mo | 93 | 12.3% | Trust & partner case studies — blocks partners, bugs, improve presented results |
| next-6mo | 304 | 40.3% | Quality of what we have — finish partial work, documentation, optimization |
| later-12mo | 82 | 10.9% | Expand & prepare — adjacent use cases, ecosystem integration, scaling |
| someday | 166 | 22.0% | Stay ready to pivot — research, polish, community process items |
| done | 109 | 14.5% | Capability inventory — completed items separated at bottom of CSV |

Key observations:
- 93 items (12%) are now-3mo — a focused, actionable near-term workload
- 304 items (40%) are next-6mo — the bulk of "finish what's started" work, especially ML/AI partials
- ML/AI dominates now-3mo (23 items) — tracking, class masking, confidence, rank rollups
- Documentation is entirely next-6mo (44 items) — strategic gap but not blocking partners immediately
- Community items are mostly someday (42/49) — important but not code work

---

## Artifacts Produced

| File | Description |
|------|-------------|
| `docs/roadmap-categorized.csv` | 862 items with category, size, type |
| `docs/roadmap-batch{1,2,3}.csv` | Raw batch outputs (can be deleted after merge) |
| `docs/claude/planning/github-index.md` | Full PR + issue title index with dates |
| `docs/claude/planning/github-summaries.jsonl` | 954 summarized GitHub entries |
| `docs/claude/planning/roadmap-deduped.jsonl` | 754 canonical items, deduped & cross-referenced |
| `docs/claude/planning/roadmap-master.csv` | Final sortable roadmap (Phase 4 output) |
| `docs/claude/planning/roadmap-distillation-plan.md` | This document |
| `docs/claude/planning/NEXT_SESSION_PROMPT.md` | Session continuation prompt |
