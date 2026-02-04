# UI Framework Migration Planning

## Overview

Planning documents for migrating the Antenna UI from Vite + React Router to a more opinionated framework. Two options are evaluated: **Next.js** and **Remix**.

**Recommendation**: Remix is better aligned with our motivations (reducing boilerplate, prescribed patterns, DRF-like experience).

---

## Document Index

### Context & Motivations

| # | Document | Description |
|---|----------|-------------|
| 01 | [Current State](./01-current-state.md) | Analysis of current UI and API architecture |
| 08 | [**Motivations**](./08-motivations.md) | Why we're considering migration (small team, patterns, maintenance) |
| 09 | [**E2E Testing Strategy**](./09-e2e-testing-strategy.md) | Playwright setup, test generation strategies, analytics-driven prioritization |

### Next.js Assessment

| # | Document | Description |
|---|----------|-------------|
| 02 | [Next.js Benefits](./02-nextjs-benefits.md) | What Next.js offers and can replace |
| 03 | [Required Changes](./03-required-changes.md) | Everything that needs to change for Next.js |
| 04 | [Custom/Bespoke](./04-custom-bespoke.md) | What stays custom (Next.js) |
| 05 | [Migration Steps](./05-migration-steps.md) | Phased implementation plan (Next.js) |
| 06 | [Questions & Risks](./06-questions-risks.md) | Risks, alternatives, benefits (Next.js) |
| 07 | [Testing & Evaluation](./07-testing-evaluation.md) | Testing plan (Next.js) |

### Remix Assessment (Recommended)

| # | Document | Description |
|---|----------|-------------|
| R1 | [Remix Benefits](./remix/01-remix-benefits.md) | What Remix offers - loaders, actions, forms |
| R2 | [Required Changes](./remix/02-required-changes.md) | Everything that needs to change for Remix |
| R3 | [Custom/Bespoke](./remix/03-custom-bespoke.md) | What stays custom (Remix) |
| R4 | [Migration Steps](./remix/04-migration-steps.md) | Phased implementation plan (Remix) |
| R5 | [Questions & Risks](./remix/05-questions-risks.md) | Risks, alternatives, benefits (Remix) |
| R6 | [Testing & Evaluation](./remix/06-testing-evaluation.md) | Testing plan (Remix) |
| R7 | [**AI-Driven Migration**](./remix/07-ai-driven-migration.md) | How Claude Code executes migration in 1-2 hours |

---

## Quick Comparison

### Current Stack
- **Build**: Vite 4.5.3
- **Routing**: React Router v6.8.2
- **State**: React Query + Context
- **Styling**: Tailwind CSS + SCSS
- **Components**: Radix UI + nova-ui-kit

### Option A: Next.js
- **Build**: Next.js 14 (App Router)
- **Routing**: File-based (app/)
- **State**: React Query + Context (keep)
- **Data loading**: Flexible (server components, client)
- **Forms**: Manual (Server Actions basic)

### Option B: Remix (Recommended)
- **Build**: Remix 2.x (Vite-based)
- **Routing**: File-based (routes/)
- **State**: Minimal (loaders handle server state)
- **Data loading**: Prescribed (loaders)
- **Forms**: First-class (`<Form>`, actions)

---

## Comparison Matrix

| Factor | Current | Next.js | Remix |
|--------|---------|---------|-------|
| Boilerplate | High | Medium | **Low** |
| Prescribed Patterns | None | Some | **Many** |
| Form Handling | Manual | Basic | **Built-in** |
| Data Flow Opinions | None | Low | **High** |
| Files to Remove | - | ~10 | **~43** |
| DRF-like Feel | No | Somewhat | **Yes** |
| Learning Curve | - | Medium | Medium |
| Community Size | - | **Largest** | Medium |
| Migration Time | - | 6-8 weeks | 6-7 weeks |

---

## Key Metrics

### Next.js Migration
| Aspect | Value |
|--------|-------|
| Estimated Duration | 6-8 weeks |
| Routes to Migrate | ~25 |
| Files to Change | ~150 |
| Custom Code Preserved | ~85% |
| Boilerplate Reduction | Low |

### Remix Migration
| Aspect | Value |
|--------|-------|
| Estimated Duration | 6-7 weeks |
| Routes to Migrate | ~25 |
| Files to Delete | ~43 (hooks → loaders) |
| Custom Code Preserved | ~85% |
| Boilerplate Reduction | **High** |

---

## Recommendation

**Go with Remix** because:

1. **Loaders replace ~22 data hooks** - prescribed pattern for data fetching
2. **Actions replace ~15 mutation hooks** - prescribed pattern for mutations
3. **URL state is built-in** - no more useFilters, useSort, usePagination
4. **Forms are first-class** - `<Form>` with automatic pending states
5. **More opinionated** - closer to "DRF for frontend" philosophy
6. **Same migration effort** - ~6-7 weeks vs 6-8 weeks for Next.js

### Suggested Approach

1. **POC (1 week)**: Migrate login + projects list + one occurrence page
2. **Evaluate**: Does it reduce boilerplate? Is the pattern clear?
3. **Decide**: Continue or reconsider
4. **Full migration (5-6 weeks)**: If POC successful

---

## Team Context

- **2 developers** + periodic interns + AI agents
- Need **prescribed patterns** for fast onboarding
- Want to **reduce custom code** maintenance burden
- Looking for **DRF-like productivity** on frontend

See [Motivations](./08-motivations.md) for full context.

---

## Created
- **Date**: 2026-02-04
- **Branch**: claude/nextjs-migration-planning-nx9Cd
- **Updated**: 2026-02-04 (added Remix assessment)
