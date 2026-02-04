# Current State of UI and API

## Overview

The Antenna UI is a React 18 single-page application (SPA) built with Vite, serving as the frontend for the Automated Monitoring of Insects ML Platform. It interfaces with a Django REST Framework backend via a versioned JSON API.

---

## UI Architecture

### Build System
- **Bundler**: Vite 4.5.3
- **Language**: TypeScript 4.4.2 (strict mode)
- **Output**: Static bundle deployed to `./build`
- **Dev Server**: Port 3000 with HMR
- **Proxy**: Dev server proxies `/api` and `/media` to Django backend

### Routing
- **Library**: React Router v6.8.2
- **Pattern**: Client-side SPA routing
- **Structure**: Nested routes with `<Outlet />` for layout composition
- **Modal Pattern**: Detail dialogs controlled via URL params (e.g., `/occurrences/:id?`)

**Route Hierarchy:**
```
/
├── /auth
│   ├── /login
│   ├── /reset-password
│   └── /reset-password-confirm
├── /projects (list)
└── /projects/:projectId
    ├── /summary
    ├── /deployments/:id?
    ├── /sessions/:id?
    ├── /captures
    ├── /occurrences/:id?
    ├── /taxa/:id?
    ├── /jobs/:id?
    ├── /collections
    ├── /exports/:id?
    ├── /pipelines/:id?
    ├── /algorithms/:id?
    ├── /processing-services/:id?
    ├── /sites, /devices, /general, /team
    ├── /default-filters, /storage, /processing
├── /terms-of-service
└── /code-of-conduct
```

### State Management

**Server State**: TanStack React Query v4.29.5
- Automatic caching and background refetching
- Query invalidation on mutations
- DevTools for debugging

**Client State**: React Context API
- `UserContext` - Authentication token and login state
- `UserInfoContext` - Current user profile
- `UserPreferencesContext` - UI preferences (localStorage-backed)
- `BreadcrumbContext` - Navigation breadcrumbs
- `CookieConsentContext` - GDPR compliance

### Data Fetching

**Pattern**: Custom hooks wrapping React Query

```typescript
// List queries
useOccurrences(params?: FetchParams) → { occurrences, total, isLoading }
useJobs(params?: FetchParams) → { jobs, total, isLoading }

// Detail queries
useOccurrenceDetails(id) → { occurrence, isLoading }
useProjectDetails(projectId) → { project, isLoading }

// Mutations
useCreateJob(onSuccess) → { createJob, isLoading, error }
useCreateIdentification(onSuccess) → { createIdentification, isLoading }
```

**HTTP Client**: Axios with auth header injection

**Query Key Pattern**: `[API_ROUTE, params]`

### Component Organization

```
ui/src/
├── components/          # Reusable UI components (filtering, forms, gallery)
├── design-system/       # Custom primitives (34 component directories)
│   ├── components/      # Button, Dialog, Table, etc.
│   └── map/             # Geospatial components
├── pages/               # Route-level components (21 page directories)
├── data-services/       # API integration
│   ├── hooks/           # React Query hooks (22 domain directories)
│   ├── models/          # Client-side model classes
│   └── constants.ts     # API routes
└── utils/               # Shared utilities and contexts
```

### Styling
- **Primary**: Tailwind CSS v3.4.14
- **Secondary**: SCSS modules for component-specific styles
- **Design Tokens**: `nova-ui-kit` library for colors and variables
- **Breakpoints**: SM (720px), MD (1024px), LG (1440px)

### Key Dependencies
| Category | Libraries |
|----------|-----------|
| UI Components | Radix UI (7 packages), nova-ui-kit, lucide-react |
| Forms | react-hook-form v7.43.9 |
| Maps | leaflet + react-leaflet |
| Charts | plotly.js + react-plotly.js |
| Utilities | lodash, date-fns, classnames |
| Monitoring | @sentry/react |

### Authentication
- **Method**: Token-based (djoser)
- **Storage**: localStorage
- **Header**: `Authorization: Token {token}`
- **Auto-logout**: On 403 responses

---

## API Architecture

### Base Configuration
- **URL**: `/api/v2/`
- **Framework**: Django REST Framework
- **Schema**: OpenAPI via drf-spectacular
- **Docs**: Swagger UI at `/api/v2/docs/`

### Versioning
- Namespace versioning (`/api/v2/`)
- Single version currently deployed

### Authentication Endpoints
```
POST /api/v2/auth/token/login/     # Get token (email + password)
POST /api/v2/auth/token/logout/    # Logout
GET  /api/v2/users/me/             # Current user
POST /api/v2/users/reset_password/ # Password reset
```

### REST Patterns
Standard CRUD for all resources:
```
GET    /api/v2/{resource}/         # List (paginated)
POST   /api/v2/{resource}/         # Create
GET    /api/v2/{resource}/{id}/    # Retrieve
PUT    /api/v2/{resource}/{id}/    # Update
DELETE /api/v2/{resource}/{id}/    # Delete
```

### Key Resources
| Resource | Endpoint | Custom Actions |
|----------|----------|----------------|
| Projects | `/projects/` | `charts/` |
| Deployments | `/deployments/` | `sync/` |
| Events | `/events/` | `timeline/` |
| Captures | `/captures/` | `star/`, `unstar/` |
| Occurrences | `/occurrences/` | `add/`, `remove/`, `suggest/` |
| Jobs | `/jobs/` | `run/`, `cancel/`, `retry/`, `tasks/`, `result/` |
| Pipelines | `/ml/pipelines/` | `test_process/` |
| Processing Services | `/ml/processing_services/` | `status/`, `register_pipelines/` |

### Pagination
- **Type**: Limit-Offset
- **Default Page Size**: 10
- **Response**: `{ count, next, previous, results, user_permissions }`

### Filtering
- Field filtering: `?field=value`
- Ordering: `?ordering=field` or `?ordering=-field`
- Search: `?search=query`
- Custom threshold filters for numeric comparisons

### Nested Resources
```
/api/v2/projects/{project_id}/members/
```

---

## Current Pain Points

### Development Experience
1. **No SSR**: Initial page load shows blank screen, then hydrates
2. **No Static Generation**: All pages require client-side data fetching
3. **Manual Route Management**: Route constants must match router config
4. **No Built-in API Routes**: Can't add BFF (Backend for Frontend) endpoints
5. **Environment Config**: Manual Vite environment variable setup

### Performance
1. **Client-side Rendering Only**: No server-side rendering for SEO or performance
2. **Large Bundle**: Single bundle for entire app (no automatic code splitting by route)
3. **Image Optimization**: Manual image handling, no built-in optimization

### SEO/Accessibility
1. **Dynamic Titles**: Managed via react-helmet-async instead of native
2. **No Metadata API**: Must manually manage Open Graph tags
3. **Crawler Issues**: SPA content not visible to crawlers without JS

### Architecture
1. **Proxy Dependency**: Development requires Vite proxy to Django
2. **No Edge/Middleware**: Can't intercept requests at edge
3. **Manual Caching**: No built-in data caching beyond React Query
