# Next.js Migration Planning

## Document Index

| # | Document | Description |
|---|----------|-------------|
| 01 | [Current State](./01-current-state.md) | Analysis of current UI and API architecture |
| 02 | [Next.js Benefits](./02-nextjs-benefits.md) | What Next.js offers and can replace |
| 03 | [Required Changes](./03-required-changes.md) | Comprehensive list of everything that needs to change |
| 04 | [Custom/Bespoke](./04-custom-bespoke.md) | What stays custom to Antenna |
| 05 | [Migration Steps](./05-migration-steps.md) | Phased implementation plan |
| 06 | [Questions & Risks](./06-questions-risks.md) | Outstanding questions, risks, alternatives, and benefits |
| 07 | [Testing & Evaluation](./07-testing-evaluation.md) | Plan for validating the migration |

---

## Quick Reference

### Current Stack
- **Build**: Vite 4.5.3
- **Routing**: React Router v6.8.2
- **State**: React Query + Context
- **Styling**: Tailwind CSS + SCSS
- **Components**: Radix UI + nova-ui-kit

### Target Stack
- **Build**: Next.js 14 (App Router)
- **Routing**: File-based (app/)
- **State**: React Query + Context (unchanged)
- **Styling**: Tailwind CSS + SCSS (unchanged)
- **Components**: Radix UI + nova-ui-kit (unchanged)

### Key Metrics

| Aspect | Value |
|--------|-------|
| Estimated Duration | 6-8 weeks |
| Routes to Migrate | ~25 |
| Files to Change | ~150 |
| Custom Code Preserved | ~85% |
| Risk Level | Medium |

### Decision Factors

**Migrate if**:
- Performance improvements are valuable
- Team has bandwidth
- Future SSR/RSC features needed

**Defer if**:
- Current performance acceptable
- Team at capacity
- Low risk tolerance

---

## Created
- **Date**: 2026-02-04
- **Branch**: claude/nextjs-migration-planning-nx9Cd
