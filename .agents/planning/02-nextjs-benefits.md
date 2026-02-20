# What Next.js Can Offer

## Overview

Next.js 14+ (App Router) provides a full-stack React framework that can replace multiple custom solutions with battle-tested, optimized built-ins. This document outlines what Next.js brings and what it can replace.

---

## Stock Modules That Replace Custom Solutions

### 1. Routing System

**Current**: React Router v6 with manual configuration

**Next.js Replacement**: File-based App Router

| Feature | Current (React Router) | Next.js App Router |
|---------|----------------------|-------------------|
| Route Definition | Explicit in `app.tsx` | Folder structure (`app/`) |
| Nested Layouts | `<Outlet />` component | `layout.tsx` files |
| Route Groups | Manual organization | `(folder)` syntax |
| Parallel Routes | Not supported | `@folder` slots |
| Intercepting Routes | Complex modal patterns | `(.)` syntax |
| Loading States | Manual with React Query | `loading.tsx` files |
| Error Boundaries | Manual setup | `error.tsx` files |
| Not Found | Manual 404 handling | `not-found.tsx` files |

**Migration Example:**
```
# Current structure
src/pages/occurrences/occurrences.tsx
src/pages/occurrence-details/occurrence-details.tsx

# Next.js structure
app/projects/[projectId]/occurrences/page.tsx
app/projects/[projectId]/occurrences/[id]/page.tsx
app/projects/[projectId]/occurrences/loading.tsx
app/projects/[projectId]/occurrences/error.tsx
```

### 2. Data Fetching

**Current**: React Query + Axios + custom hooks

**Next.js Options**:

| Pattern | Use Case | Benefit |
|---------|----------|---------|
| Server Components | Initial data load | No client bundle, faster TTI |
| `fetch()` with caching | Server-side requests | Automatic deduplication |
| Server Actions | Mutations | Type-safe, no API routes needed |
| React Query (kept) | Real-time updates | Client-side caching |

**Hybrid Approach** (Recommended):
```typescript
// Server Component for initial data
async function OccurrencesPage({ params }) {
  const occurrences = await fetchOccurrences(params.projectId)
  return <OccurrencesList initialData={occurrences} />
}

// Client Component for interactivity
'use client'
function OccurrencesList({ initialData }) {
  const { data } = useOccurrences({ initialData })
  // React Query handles updates, initial data from server
}
```

### 3. Image Optimization

**Current**: Manual `<img>` tags, no optimization

**Next.js Replacement**: `next/image` component

| Feature | Benefit |
|---------|---------|
| Automatic WebP/AVIF | Smaller file sizes |
| Lazy loading | Built-in with blur placeholder |
| Responsive images | `sizes` prop generates srcset |
| Remote optimization | Configurable `remotePatterns` |
| Priority loading | LCP optimization |

**For Antenna**: Critical for gallery views with many insect images

### 4. Metadata & SEO

**Current**: react-helmet-async for dynamic titles

**Next.js Replacement**: Metadata API

```typescript
// Static metadata
export const metadata = {
  title: 'Occurrences | Antenna',
  description: 'Browse species occurrences',
}

// Dynamic metadata
export async function generateMetadata({ params }) {
  const project = await getProject(params.projectId)
  return { title: `${project.name} | Antenna` }
}
```

### 5. Environment Variables

**Current**: Vite's `VITE_` prefix, manual setup

**Next.js Replacement**: Built-in env handling

| Prefix | Visibility | Use Case |
|--------|------------|----------|
| `NEXT_PUBLIC_` | Client + Server | Public config |
| (none) | Server only | API keys, secrets |

### 6. API Routes (Backend for Frontend)

**Current**: Not available - all requests go directly to Django

**Next.js Addition**: Route Handlers

```typescript
// app/api/aggregate/route.ts
export async function GET(request: Request) {
  // Aggregate multiple Django API calls
  const [projects, user] = await Promise.all([
    fetch(`${DJANGO_URL}/api/v2/projects/`),
    fetch(`${DJANGO_URL}/api/v2/users/me/`)
  ])
  return Response.json({ projects, user })
}
```

**Use Cases**:
- Aggregate multiple Django endpoints
- Add server-side caching layer
- Implement BFF patterns
- Add rate limiting or logging

### 7. Middleware

**Current**: Not available

**Next.js Addition**: Edge Middleware

```typescript
// middleware.ts
export function middleware(request: NextRequest) {
  // Authentication check
  const token = request.cookies.get('auth_token')
  if (!token && request.nextUrl.pathname.startsWith('/projects')) {
    return NextResponse.redirect(new URL('/auth/login', request.url))
  }
}
```

**Use Cases**:
- Authentication redirects
- Geolocation-based routing
- A/B testing
- Request logging

### 8. Caching & Revalidation

**Current**: React Query client-side caching only

**Next.js Addition**: Multi-layer caching

| Layer | Control | Use Case |
|-------|---------|----------|
| Data Cache | `fetch` options | API response caching |
| Full Route Cache | Static/dynamic | Pre-rendered pages |
| Router Cache | Automatic | Client-side navigation |

```typescript
// Cache for 1 hour, revalidate in background
fetch(url, { next: { revalidate: 3600 } })

// Revalidate on demand
import { revalidatePath } from 'next/cache'
revalidatePath('/projects/[projectId]/occurrences')
```

---

## Performance Benefits

### 1. Rendering Strategies

| Strategy | When to Use | Antenna Use Case |
|----------|-------------|------------------|
| Static (SSG) | Content rarely changes | Terms, Code of Conduct |
| Server (SSR) | Personalized/fresh data | Project dashboards |
| Streaming | Large data sets | Occurrence lists |
| Client | Highly interactive | Identification dialogs |

### 2. Code Splitting

**Current**: Manual with React.lazy()

**Next.js**: Automatic per-route code splitting

- Each page only loads its required JavaScript
- Shared chunks extracted automatically
- Prefetching on link hover

### 3. Font Optimization

**Current**: Manual font loading

**Next.js**: `next/font`
- Zero layout shift
- Automatic font subsetting
- Self-hosted (privacy)

---

## Developer Experience Benefits

### 1. TypeScript Integration
- Stricter route type safety
- Auto-generated types for params
- Server Action type inference

### 2. Fast Refresh
- Comparable to Vite HMR
- State preservation
- Error overlay

### 3. Built-in Dev Tools
- React DevTools integration
- Route inspector
- Build analysis (`next build --analyze`)

### 4. Deployment
- Zero-config Vercel deployment
- Docker support
- Node.js server or static export

---

## What Can Be Replaced vs Kept

### Replace

| Current | Next.js Replacement |
|---------|-------------------|
| React Router | App Router |
| react-helmet-async | Metadata API |
| Vite | Next.js bundler (Turbopack) |
| Manual image handling | next/image |
| Vite proxy config | rewrites in next.config.js |
| Manual route constants | File-based routing |
| Manual loading states | loading.tsx |
| Manual error boundaries | error.tsx |

### Keep

| Library | Reason |
|---------|--------|
| React Query | Real-time updates, optimistic mutations |
| react-hook-form | Form handling (no Next.js equivalent) |
| Tailwind CSS | Styling (works great with Next.js) |
| Radix UI | Accessible components |
| nova-ui-kit | Design tokens |
| Leaflet | Maps (no Next.js map solution) |
| Plotly | Charts |
| Axios | Can keep or switch to native fetch |
| lodash/date-fns | Utilities |

### Evaluate

| Library | Consideration |
|---------|--------------|
| Axios | Could switch to native fetch() for server components |
| Sentry | Use @sentry/nextjs instead |
| classnames | Could use clsx or Tailwind's cn() |

---

## Feature Comparison Summary

| Feature | Current Stack | Next.js | Improvement |
|---------|--------------|---------|-------------|
| Initial Load | Client render | Server render | 40-60% faster FCP |
| SEO | Poor (SPA) | Excellent | Crawlable content |
| Code Splitting | Manual | Automatic | Smaller bundles |
| Image Optimization | None | Built-in | Better Core Web Vitals |
| API Aggregation | None | Route Handlers | Reduce waterfalls |
| Caching | React Query | Multi-layer | Better performance |
| Loading States | Manual | Conventions | Less boilerplate |
| Error Handling | Manual | Conventions | Consistent UX |
| Type Safety | Good | Excellent | Safer routing |
