# What Stays Custom/Bespoke

## Overview

While Next.js provides many built-in features, significant portions of the Antenna application are domain-specific and will remain custom. This document identifies components and patterns that cannot be replaced by Next.js stock modules.

---

## 1. Domain Models & Business Logic

### Client-Side Model Classes

These TypeScript classes encapsulate business logic specific to Antenna:

```
data-services/models/
├── occurrence.ts       # Occurrence entity with computed properties
├── detection.ts        # Detection bounding box logic
├── classification.ts   # ML classification results
├── identification.ts   # Human identification workflow
├── deployment.ts       # Monitoring station logic
├── event.ts            # Temporal event grouping
├── job.ts              # ML job state machine
├── pipeline.ts         # ML pipeline configuration
└── project.ts          # Project with member permissions
```

**Key Custom Logic Examples:**

```typescript
// Occurrence model - domain-specific computed properties
class Occurrence {
  get displayName(): string { /* taxonomy display logic */ }
  get bestClassification(): Classification { /* ranking logic */ }
  userAgreed(userId: string, taxonId?: string): boolean { /* agreement logic */ }
  hasConflictingIdentifications(): boolean { /* conflict detection */ }
}

// Job model - state machine for ML jobs
class Job {
  canStart(): boolean { /* state validation */ }
  canCancel(): boolean { /* running job check */ }
  getProgressPercentage(): number { /* stage calculation */ }
}
```

**Migration**: These stay exactly as-is. No Next.js equivalent exists.

---

## 2. Custom Design System

### nova-ui-kit Integration

The design token system from `nova-ui-kit` is deeply integrated:

```
design-system/
├── components/
│   ├── button/          # Custom button variants
│   ├── dialog/          # Modal dialogs
│   ├── table/           # Data tables with sorting
│   ├── gallery/         # Image gallery grid
│   ├── pagination/      # Custom pagination
│   ├── icon-button/     # Icon actions
│   ├── tooltip/         # Hover tooltips
│   ├── select/          # Dropdown selects
│   ├── tabs/            # Tab navigation
│   ├── accordion/       # Collapsible sections
│   └── ... (34 component types)
└── variables/
    └── variables.scss   # SCSS variables
```

**Migration**: All 34+ design system components remain unchanged. They're framework-agnostic React components that work with Next.js.

### Radix UI Wrappers

Custom wrappers around Radix primitives with Antenna-specific styling:
- `Dialog` - Project dialogs with specific layouts
- `DropdownMenu` - Action menus with icons
- `Select` - Styled selects with search
- `Tooltip` - Consistent tooltip styling
- `Accordion` - Settings accordions

---

## 3. ML Pipeline Visualization

### Job Progress UI

Complex visualization of ML pipeline stages:

```
pages/job-details/
├── job-details.tsx              # Main job view
├── job-stage-label/             # Stage status indicators
│   └── job-stage-label.tsx
└── job-actions/
    ├── queue-job.tsx           # Start job action
    ├── cancel-job.tsx          # Cancel running job
    └── retry-job.tsx           # Retry failed job
```

**Custom Logic:**
- Real-time progress polling
- Stage-by-stage progress visualization
- Error display with stack traces
- Log streaming from Celery

### Pipeline Configuration

```
pages/pipeline-details/
├── pipeline-details-dialog.tsx
├── pipeline-stages.tsx          # Stage configuration
└── pipeline-algorithms.tsx      # Algorithm selection
```

---

## 4. Species Identification System

### Identification Workflow

The core ML identification workflow is entirely custom:

```
pages/occurrence-details/
├── occurrence-details.tsx       # Detail view with all info
├── agree/
│   └── agree.tsx               # Agreement workflow
├── suggest-id/
│   ├── suggest-id.tsx          # Taxa suggestion with autocomplete
│   └── suggest-id-popover.tsx  # Suggestion dropdown
├── identification-card/
│   ├── human-identification.tsx # Human ID display
│   └── machine-prediction.tsx   # ML prediction display
├── id-quick-actions/
│   ├── id-button.tsx           # Quick ID buttons
│   └── id-quick-actions.tsx    # Action bar
├── status-label/
│   └── status-label.tsx        # Verification status
└── taxonomy-info/
    └── taxonomy-info.tsx       # Taxonomic hierarchy display
```

**Custom Features:**
- Taxa autocomplete with fuzzy matching
- Agreement/disagreement workflow
- Confidence score visualization
- Taxonomy tree navigation
- ML prediction comparison

---

## 5. Geospatial Components

### Map Integration

Leaflet-based mapping for deployment locations:

```
design-system/map/
├── map.tsx                     # Base map component
├── map-controls.tsx            # Zoom, layers
└── map-markers.tsx             # Deployment markers

pages/deployment-details/
└── deployment-details-form/
    └── section-location/
        ├── location-map/
        │   └── location-map.tsx # Editable location picker
        └── geo-search/
            └── geo-search.tsx   # Address search
```

**Custom Features:**
- Deployment location picker with drag-and-drop
- Geosearch integration
- Custom marker clustering for multiple deployments
- Satellite/terrain layer switching

---

## 6. Image Gallery System

### Gallery Components

Custom gallery for browsing capture images:

```
components/gallery/
├── gallery.tsx                 # Main gallery grid
├── gallery-item.tsx            # Individual image card
├── gallery-filters.tsx         # Filter controls
└── gallery-navigation.tsx      # Keyboard navigation

pages/occurrences/
├── occurrence-gallery.tsx      # Occurrence thumbnail grid
└── occurrence-navigation.tsx   # Prev/next navigation

pages/captures/
├── capture-gallery.tsx         # Source image gallery
└── capture-columns.tsx         # Table/gallery toggle
```

**Custom Features:**
- Infinite scroll with virtualization
- Bounding box overlays on images
- Thumbnail generation handling
- Keyboard navigation (arrow keys)
- Selection mode for batch operations

---

## 7. Filtering System

### Complex Filter Components

Domain-specific filtering for occurrences and captures:

```
components/filtering/
├── filter-panel.tsx            # Main filter container
├── filter-chips.tsx            # Active filter display
├── filter-presets.tsx          # Saved filter presets
├── filters/
│   ├── taxon-filter.tsx        # Taxonomy tree filter
│   ├── score-filter.tsx        # Confidence threshold
│   ├── date-range-filter.tsx   # Temporal filtering
│   ├── deployment-filter.tsx   # Location filtering
│   ├── event-filter.tsx        # Event grouping
│   └── status-filter.tsx       # Verification status
```

**Custom Features:**
- Hierarchical taxa filtering with tree navigation
- Score threshold sliders
- Date range pickers with presets
- Multi-select deployment picker
- Filter persistence in URL params

### Filter Hooks

```typescript
// utils/useFilters.ts
export function useFilters() {
  // URL-synchronized filter state
  // Filter combination logic
  // Clear/reset functionality
}

// utils/useSort.ts
export function useSort() {
  // Column sorting state
  // Multi-column sort support
}

// utils/usePagination.ts
export function usePagination() {
  // Offset-based pagination
  // Page size preferences
}
```

---

## 8. Data Export System

### Export Configuration

```
pages/project/exports/
├── exports.tsx                 # Export list
└── exports-columns.tsx         # Export status table

pages/export-details/
└── export-details-dialog.tsx   # Export configuration
```

**Custom Features:**
- Format selection (CSV, JSON, Darwin Core)
- Field mapping configuration
- Progress tracking for large exports
- Download management

---

## 9. Processing Service Management

### Service Health Monitoring

```
pages/processing-service-details/
├── processing-service-details-dialog.tsx
└── processing-service-pipelines.tsx

pages/project/processing-services/
├── processing-services.tsx
├── processing-services-columns.tsx
├── connection-status.tsx        # Health indicator
└── status-info/
    └── status-info.tsx         # Detailed status
```

**Custom Features:**
- Real-time health check polling
- Pipeline registration workflow
- Error diagnostics display
- Service URL configuration

---

## 10. Project Configuration

### Settings Pages

```
pages/project/
├── general/general.tsx          # Basic settings
├── team/                        # Member management (nested route)
├── default-filters/             # Default filter config
├── storage/                     # S3 storage config
└── processing/                  # ML processing settings
```

### Forms

```
pages/project-details/
├── default-filters-form.tsx     # Taxa inclusion/exclusion
├── processing-form.tsx          # Pipeline defaults
├── pipelines-select.tsx         # Pipeline multi-select
└── project-details-form.tsx     # General settings
```

---

## 11. React Query Hooks (Modified but Custom)

All domain-specific data fetching hooks remain custom:

```
data-services/hooks/
├── algorithms/useAlgorithms.ts
├── captures/useCaptures.ts
├── classifications/useClassifications.ts
├── collections/useCollections.ts
├── deployments/useDeployments.ts
├── detections/useDetections.ts
├── events/useEvents.ts
├── exports/useExports.ts
├── identifications/useIdentifications.ts
├── jobs/useJobs.ts
├── members/useMembers.ts
├── occurrences/useOccurrences.ts
├── pipelines/usePipelines.ts
├── processing-services/useProcessingServices.ts
├── projects/useProjects.ts
├── sites/useSites.ts
├── storage/useStorage.ts
├── taxa/useTaxa.ts
└── users/useUsers.ts
```

**Modification**: These hooks will be adapted for SSR hydration but business logic remains.

---

## 12. Utility Functions

### Domain Utilities

```typescript
// Format helpers
formatTaxonName(taxon: Taxon): string
formatConfidenceScore(score: number): string
formatTimestamp(date: Date, format: string): string

// Validation helpers
validateDeploymentLocation(lat: number, lng: number): boolean
validateTaxonSelection(taxon: Taxon, project: Project): boolean

// Transformation helpers
convertServerOccurrence(data: ServerOccurrence): Occurrence
buildFilterQueryString(filters: Filter[]): string
```

---

## Summary: Custom vs Stock

### Stays 100% Custom
| Category | Components | Reason |
|----------|------------|--------|
| Domain Models | 10+ classes | Business logic |
| Design System | 34+ components | Brand/UX |
| ML Visualization | Job progress, pipelines | Domain-specific |
| Identification UI | Agree/suggest/taxonomy | Core workflow |
| Maps | Leaflet integration | No Next.js equivalent |
| Gallery | Image grid/navigation | Custom UX |
| Filtering | Taxa/score/date filters | Domain-specific |
| Export | Configuration/progress | Domain-specific |
| React Query Hooks | 20+ hooks | API integration |

### Modified but Mostly Custom
| Category | Change |
|----------|--------|
| Page components | Add 'use client', update imports |
| Contexts | Add cookie support for SSR |
| Data hooks | Add SSR hydration support |

### Replaced by Next.js
| Category | Replacement |
|----------|-------------|
| Router config | File-based routing |
| Route constants | Can simplify |
| Loading states | loading.tsx |
| Error boundaries | error.tsx |
| Metadata | Metadata API |
| Image tags | next/image (partial) |

---

## Effort Estimate by Category

| Category | Files | Effort | Notes |
|----------|-------|--------|-------|
| Domain Models | 10 | None | No changes needed |
| Design System | 50+ | Low | Add 'use client' where needed |
| Page Components | 21 | Medium | Convert to page.tsx format |
| Data Hooks | 22 | Medium | Add SSR support |
| Utilities | 15 | Low | Mostly unchanged |
| Contexts | 5 | Medium | Cookie + localStorage |
| Filters | 10 | Low | Unchanged |
| Maps | 5 | Low | Add 'use client' |
| Gallery | 8 | Low | Add 'use client' |

**Total custom code preserved**: ~85% of application logic
**Total code requiring modification**: ~40% (mostly adding directives)
