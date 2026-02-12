# What Stays Custom/Bespoke (Remix)

## Overview

While Remix provides more built-in patterns than Next.js, significant portions of the Antenna application remain domain-specific. This document is shorter than the Next.js equivalent because many items are identical.

---

## What Stays Identical to Current

These require no changes beyond possibly adding client-side markers:

### 1. Domain Models
All model classes in `data-services/models/` stay unchanged:
- `Occurrence`, `Detection`, `Classification`
- `Identification`, `Job`, `Pipeline`
- `Project`, `Deployment`, `Event`

### 2. Design System
All 34+ components in `design-system/` stay unchanged:
- Button, Dialog, Table, Gallery, etc.
- nova-ui-kit integration
- Radix UI wrappers

### 3. Visualization Components
- Leaflet map integration
- Plotly charts
- Gallery grid with bounding boxes

### 4. Identification Workflow UI
- Taxa autocomplete
- Agree/disagree buttons
- Prediction comparison views

### 5. Complex Filtering UI
- Taxa tree filter
- Score threshold sliders
- Date range pickers

---

## What Changes (Simplified in Remix)

### Data Fetching Hooks → Loaders

**Before** (22 hook directories):
```
data-services/hooks/
├── occurrences/useOccurrences.ts
├── occurrences/useOccurrenceDetails.ts
├── jobs/useJobs.ts
├── jobs/useJobDetails.ts
└── ... (18 more)
```

**After** (Embedded in routes):
```
app/routes/
├── projects.$projectId.occurrences.tsx  // loader inline
├── projects.$projectId.jobs.tsx         // loader inline
└── ...

app/services/  // Shared fetch logic
├── occurrences.server.ts
├── jobs.server.ts
└── ...
```

**Net change**: 22 hook files → 10 service files + loaders in routes

### Mutation Hooks → Actions

**Before** (15+ mutation hooks):
```typescript
useCreateJob()
useCreateIdentification()
useAgreeWithPrediction()
useUpdateDeployment()
useSyncDeployment()
// etc.
```

**After** (Actions in route files):
```typescript
// routes/projects.$projectId.jobs.tsx
export async function action({ request }: ActionFunctionArgs) {
  const formData = await request.formData()
  const intent = formData.get('intent')
  // Handle create, update, delete based on intent
}
```

**Net change**: 15 hook files → 0 (logic moves to routes)

### URL State Hooks → Built-in

**Before**:
```typescript
// Custom hooks for URL sync
useFilters()
useSort()
usePagination()
```

**After**:
```typescript
// Just use Remix's useSearchParams
const [searchParams, setSearchParams] = useSearchParams()
```

**Net change**: 3 hook files → 0

---

## What Needs 'use client' Equivalent

Remix uses `clientLoader` and `clientAction` for client-side code, but most interactive components work automatically. Components needing explicit client-side:

### Must Be Client-Only (Dynamic Import)

```typescript
// Maps - Leaflet doesn't work server-side
const LocationMap = lazy(() => import('~/components/location-map'))

// Charts - Plotly doesn't work server-side
const Chart = lazy(() => import('~/components/chart'))
```

### Work Automatically (No Changes)

- All Radix UI components (Dialog, Dropdown, etc.)
- react-hook-form
- Event handlers (onClick, onChange)
- useState, useEffect

Remix is more permissive than Next.js RSC—components with hooks work without special directives.

---

## Custom Code Inventory (Post-Migration)

| Category | Files | Status |
|----------|-------|--------|
| Domain Models | 10 | Unchanged |
| Design System | 50+ | Unchanged |
| Visualization | 8 | Unchanged, lazy load |
| Route Files | 25 | New (replace pages) |
| Service Files | 10 | New (shared fetch logic) |
| Utilities | 10 | Mostly unchanged |
| **Total Custom** | ~113 | Reduced from ~145 |

### Deleted (No Longer Needed)

| Category | Files Removed | Reason |
|----------|---------------|--------|
| Data hooks | 22 | Replaced by loaders |
| Mutation hooks | 15 | Replaced by actions |
| URL state hooks | 3 | Built into Remix |
| Router config | 1 | File-based routing |
| Entry points | 2 | Remix handles |

**Total removed**: ~43 files

---

## What You Still Need External Libraries For

| Need | Library | Notes |
|------|---------|-------|
| Complex form validation | react-hook-form | Keep for complex forms |
| Tables with sorting | TanStack Table | Still need this |
| i18n | remix-i18next | If/when needed |
| Maps | Leaflet | No alternative |
| Charts | Plotly | No alternative |
| Design tokens | nova-ui-kit | Keep as-is |
| Accessible primitives | Radix UI | Keep as-is |

---

## Summary

Remix reduces custom code primarily in:
1. **Data fetching** - Loaders replace hooks
2. **Mutations** - Actions replace hooks
3. **URL state** - Built-in useSearchParams
4. **Loading states** - useNavigation

Custom code preserved:
1. **Domain models** - 100%
2. **UI components** - 100%
3. **Visualizations** - 100%
4. **Business logic** - 100%

**Net reduction**: ~30% fewer files, ~40% less glue code
