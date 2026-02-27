# Migration Motivations

## Team Context

### Team Size & Composition
- **2 full-time developers**
- **Periodic interns** (need clear patterns to onboard quickly)
- **AI agents** (benefit from consistent, predictable code structures)

This is a small team maintaining a complex ML platform. Every architectural decision must optimize for:
1. **Onboarding speed** - New contributors (human or AI) must understand patterns quickly
2. **Maintenance burden** - Less custom code = fewer bugs to own
3. **Feature velocity** - Spend time on domain logic, not infrastructure

---

## Core Motivations

### 1. Reduce Boilerplate Code

**Current State**: The React ecosystem requires assembling many libraries and writing glue code:
- Route definitions separate from file structure
- Custom hooks for every data fetching pattern
- Manual loading/error state handling
- Custom table sorting logic
- Form submission patterns vary by component

**Desired State**: Convention-over-configuration where common patterns are built-in:
- File = route (no configuration)
- Data loading patterns are prescribed
- Loading/error states have standard locations
- Common UI patterns (tables, forms) have established solutions

### 2. Stop Reinventing Established Patterns

**Problem**: The current codebase contains custom implementations of things the open-source community has already solved:
- Custom pagination logic
- Custom filter URL synchronization
- Custom table sorting
- Custom loading state management
- Custom error boundary setup

**Cost of Custom Solutions**:
- Bugs we own (instead of community maintaining)
- Documentation we must write
- Patterns interns/AI must learn
- Edge cases we discover over time

**Desired State**: Use framework conventions and community-maintained solutions wherever possible. Custom code only for domain-specific logic (species identification, ML pipelines, etc.).

### 3. Opinionated Framework Benefits

**Why Opinions Matter for Small Teams**:

| Aspect | Unopinionated | Opinionated |
|--------|---------------|-------------|
| Decision fatigue | High - choose everything | Low - follow conventions |
| Onboarding | "Here's how WE do it" | "Here's how everyone does it" |
| Documentation | Must write internal docs | External docs exist |
| AI assistance | Must explain patterns | AI knows standard patterns |
| Bug fixes | We maintain | Community maintains |
| Code review | Debate approaches | Standard is clear |

**Django/DRF as Model**: The backend uses Django REST Framework, which provides:
- Serializers (data validation + transformation)
- ViewSets (CRUD with minimal code)
- Permissions (declarative access control)
- Filtering (query params to queryset)
- Pagination (standardized patterns)

We want similar leverage on the frontend.

### 4. Established Places for Things

**Current Ambiguity**:
- Where does a new API hook go? (`data-services/hooks/[domain]/`)
- Where does form validation live? (in component? in hook? in utility?)
- How do we handle optimistic updates? (varies by feature)
- Where do loading states go? (inline? wrapper? context?)

**Desired Clarity**: Framework conventions that answer:
- "Where does data loading code go?" → Loader function
- "Where does mutation code go?" → Action function
- "Where does loading UI go?" → loading.tsx / pending state
- "Where does error UI go?" → error.tsx / error boundary

### 5. Specific Pain Points

#### Routing
- **Current**: Manual route definitions in `app.tsx`, must keep in sync with components
- **Desired**: File-based routing where structure = routes

#### Data Fetching + UI Sync
- **Current**: React Query hooks with varying patterns, manual cache invalidation
- **Desired**: Prescribed patterns for loading data, automatic revalidation

#### Table Sorting
- **Current**: Custom `useSort` hook, manual implementation per table
- **Desired**: Standard table solution with sorting/filtering built-in

#### Forms with Mixed Content
- **Current**: react-hook-form + manual file handling + custom submission logic
- **Desired**: Framework-level form handling that covers common cases

#### Internationalization
- **Current**: Not implemented
- **Desired**: Built-in i18n support when needed

---

## What We're NOT Optimizing For

1. **Maximum Performance** - Current performance is acceptable
2. **SEO** - App is authenticated, crawlers don't matter
3. **Server-Side Rendering** - Nice to have, not the driver
4. **Cutting-Edge Features** - Stability over novelty

---

## Success Criteria for Migration

A successful migration would mean:

1. **Interns can add features faster** by following established patterns
2. **AI agents produce better code** because patterns are standard/documented
3. **Bug count decreases** because we use community-maintained solutions
4. **Code reviews are faster** because "the right way" is clear
5. **Less custom code to maintain** overall
6. **Documentation exists externally** (framework docs, tutorials, Stack Overflow)

---

## Framework Evaluation Criteria

When evaluating Next.js, Remix, or alternatives, we prioritize:

| Criterion | Weight | Notes |
|-----------|--------|-------|
| Convention-over-configuration | High | Reduces decisions |
| Data loading patterns | High | Core pain point |
| Form handling | High | Core pain point |
| Community size | Medium | Affects available help |
| Ecosystem maturity | Medium | Affects library availability |
| Learning resources | Medium | Affects onboarding |
| Performance | Low | Current is acceptable |
| SSR capabilities | Low | Not a driver |

---

## Summary

We're a small team that needs to maximize leverage. Every line of custom infrastructure code is:
- A line we must maintain
- A pattern we must document
- A decision we must explain to new contributors
- A potential bug we own

The ideal framework acts like DRF does for our backend: providing sensible defaults, clear conventions, and community-maintained solutions for common patterns, so we can focus our limited engineering time on what makes Antenna unique—not on reinventing forms, tables, and data loading.
