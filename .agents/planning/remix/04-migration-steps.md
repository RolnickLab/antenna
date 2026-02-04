# Migration Steps (Remix)

## Overview

This document outlines a phased approach to migrating from Vite + React Router to Remix. The migration leverages the fact that Remix is built on React Router, making navigation patterns familiar.

---

## Phase 0: Preparation (1-2 days)

### 0.1 Team Preparation
- [ ] Read Remix tutorial: https://remix.run/docs/en/main/start/tutorial
- [ ] Review Remix conventions documentation
- [ ] Set up local Remix project to experiment

### 0.2 Dependency Audit
Verify compatibility:

| Library | Remix Compatible | Notes |
|---------|------------------|-------|
| react-hook-form | ✅ | Works as-is |
| tailwindcss | ✅ | Official guide exists |
| Radix UI | ✅ | Works as-is |
| nova-ui-kit | ✅ | Works as-is |
| leaflet | ⚠️ | Needs lazy loading |
| plotly | ⚠️ | Needs lazy loading |
| @sentry/react | ⚠️ | Use @sentry/remix |

### 0.3 Create Migration Branch
```bash
git checkout -b feature/remix-migration
```

---

## Phase 1: Parallel Setup (2-3 days)

### 1.1 Initialize Remix

```bash
cd ui

# Create Remix app alongside existing code
npx create-remix@latest --template remix-run/remix/templates/vite

# Or manual setup
npm install @remix-run/node @remix-run/react @remix-run/serve isbot
npm install -D @remix-run/dev vite
```

### 1.2 Create vite.config.ts for Remix

```typescript
// vite.config.ts
import { vitePlugin as remix } from '@remix-run/dev'
import { defineConfig } from 'vite'
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  plugins: [
    remix({
      ignoredRouteFiles: ['**/*.css'],
    }),
    tsconfigPaths(),
  ],
  server: {
    port: 3001,  // Different port during migration
    proxy: {
      '/api': {
        target: process.env.API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/media': {
        target: process.env.API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

### 1.3 Create Root Layout

```typescript
// app/root.tsx
import {
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useNavigation,
} from '@remix-run/react'
import type { LinksFunction } from '@remix-run/node'

import stylesheet from '~/styles/tailwind.css?url'

export const links: LinksFunction = () => [
  { rel: 'stylesheet', href: stylesheet },
]

export function Layout({ children }: { children: React.ReactNode }) {
  const navigation = useNavigation()
  const isLoading = navigation.state === 'loading'

  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        {isLoading && <GlobalLoadingBar />}
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  )
}

export default function App() {
  return <Outlet />
}

function GlobalLoadingBar() {
  return (
    <div className="fixed top-0 left-0 right-0 h-1 bg-blue-500 animate-pulse z-50" />
  )
}
```

### 1.4 Create Session Management

```typescript
// app/sessions.server.ts
import { createCookieSessionStorage, redirect } from '@remix-run/node'

const sessionSecret = process.env.SESSION_SECRET
if (!sessionSecret) {
  throw new Error('SESSION_SECRET must be set')
}

const sessionStorage = createCookieSessionStorage({
  cookie: {
    name: '__antenna_session',
    httpOnly: true,
    path: '/',
    sameSite: 'lax',
    secrets: [sessionSecret],
    secure: process.env.NODE_ENV === 'production',
    maxAge: 60 * 60 * 24 * 30, // 30 days
  },
})

export async function getSession(request: Request) {
  return sessionStorage.getSession(request.headers.get('Cookie'))
}

export async function getToken(request: Request): Promise<string | null> {
  const session = await getSession(request)
  return session.get('token')
}

export async function requireAuth(request: Request): Promise<string> {
  const token = await getToken(request)
  if (!token) {
    const url = new URL(request.url)
    throw redirect(`/auth/login?redirectTo=${url.pathname}`)
  }
  return token
}

export async function createUserSession(
  token: string,
  redirectTo: string
) {
  const session = await sessionStorage.getSession()
  session.set('token', token)
  return redirect(redirectTo, {
    headers: {
      'Set-Cookie': await sessionStorage.commitSession(session),
    },
  })
}

export async function destroySession(request: Request) {
  const session = await getSession(request)
  return redirect('/auth/login', {
    headers: {
      'Set-Cookie': await sessionStorage.destroySession(session),
    },
  })
}
```

### 1.5 Create Base Service Utilities

```typescript
// app/services/api.server.ts
const API_URL = process.env.API_URL || 'http://localhost:8000'

export async function apiRequest<T>(
  endpoint: string,
  token: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_URL}${endpoint}`

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Token ${token}`,
      ...options.headers,
    },
  })

  if (!response.ok) {
    throw new Response(`API Error: ${response.statusText}`, {
      status: response.status,
    })
  }

  return response.json()
}

export function buildQueryString(
  params: Record<string, string | number | null | undefined>
): string {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      searchParams.set(key, String(value))
    }
  })
  return searchParams.toString()
}
```

### 1.6 Set Up Tailwind

```typescript
// app/styles/tailwind.css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Import existing custom styles */
@import '../../src/index.css';
```

```javascript
// tailwind.config.js - update content paths
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    // Keep old paths during migration
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  // ... rest unchanged
}
```

---

## Phase 2: Core Routes Migration (1 week)

### 2.1 Migrate Authentication Routes

```typescript
// app/routes/auth.login.tsx
import { json, redirect, type ActionFunctionArgs, type LoaderFunctionArgs } from '@remix-run/node'
import { Form, useActionData, useNavigation, useSearchParams } from '@remix-run/react'
import { createUserSession, getToken } from '~/sessions.server'

export async function loader({ request }: LoaderFunctionArgs) {
  // Redirect if already logged in
  const token = await getToken(request)
  if (token) {
    return redirect('/projects')
  }
  return json({})
}

export async function action({ request }: ActionFunctionArgs) {
  const formData = await request.formData()
  const email = formData.get('email')
  const password = formData.get('password')
  const redirectTo = formData.get('redirectTo') || '/projects'

  // Validate
  if (!email || !password) {
    return json(
      { errors: { form: 'Email and password are required' } },
      { status: 400 }
    )
  }

  // Authenticate
  const response = await fetch(`${process.env.API_URL}/api/v2/auth/token/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!response.ok) {
    return json(
      { errors: { form: 'Invalid email or password' } },
      { status: 401 }
    )
  }

  const { auth_token } = await response.json()
  return createUserSession(auth_token, redirectTo as string)
}

export default function Login() {
  const [searchParams] = useSearchParams()
  const actionData = useActionData<typeof action>()
  const navigation = useNavigation()
  const isSubmitting = navigation.state === 'submitting'

  return (
    <div className="min-h-screen flex items-center justify-center">
      <Form method="post" className="w-full max-w-md space-y-4">
        <input
          type="hidden"
          name="redirectTo"
          value={searchParams.get('redirectTo') || '/projects'}
        />

        <h1 className="text-2xl font-bold">Log in to Antenna</h1>

        {actionData?.errors?.form && (
          <div className="bg-red-100 text-red-700 p-3 rounded">
            {actionData.errors.form}
          </div>
        )}

        <div>
          <label htmlFor="email" className="block text-sm font-medium">
            Email
          </label>
          <input
            type="email"
            name="email"
            id="email"
            required
            className="mt-1 block w-full rounded border px-3 py-2"
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium">
            Password
          </label>
          <input
            type="password"
            name="password"
            id="password"
            required
            className="mt-1 block w-full rounded border px-3 py-2"
          />
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {isSubmitting ? 'Logging in...' : 'Log in'}
        </button>
      </Form>
    </div>
  )
}
```

### 2.2 Migrate Projects List

```typescript
// app/routes/projects._index.tsx
import { json, type LoaderFunctionArgs } from '@remix-run/node'
import { Link, useLoaderData } from '@remix-run/react'
import { requireAuth } from '~/sessions.server'
import { getProjects } from '~/services/projects.server'

export async function loader({ request }: LoaderFunctionArgs) {
  const token = await requireAuth(request)
  const projects = await getProjects(token)
  return json({ projects })
}

export default function ProjectsList() {
  const { projects } = useLoaderData<typeof loader>()

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Projects</h1>
        <Link
          to="/projects/new"
          className="bg-blue-600 text-white px-4 py-2 rounded"
        >
          New Project
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {projects.results.map((project) => (
          <Link
            key={project.id}
            to={`/projects/${project.id}`}
            className="block p-4 border rounded hover:shadow-md"
          >
            <h2 className="font-semibold">{project.name}</h2>
            <p className="text-gray-600 text-sm">{project.description}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}

// app/services/projects.server.ts
import { apiRequest } from './api.server'

export async function getProjects(token: string) {
  return apiRequest<{ results: Project[]; count: number }>(
    '/api/v2/projects/',
    token
  )
}
```

### 2.3 Migrate Project Layout

```typescript
// app/routes/projects.$projectId.tsx
import { json, type LoaderFunctionArgs } from '@remix-run/node'
import { Outlet, useLoaderData, useLocation } from '@remix-run/react'
import { requireAuth } from '~/sessions.server'
import { getProject } from '~/services/projects.server'
import { Sidebar } from '~/components/sidebar'
import { Header } from '~/components/header'

export async function loader({ params, request }: LoaderFunctionArgs) {
  const token = await requireAuth(request)
  const project = await getProject(params.projectId!, token)
  return json({ project })
}

export default function ProjectLayout() {
  const { project } = useLoaderData<typeof loader>()

  return (
    <div className="flex h-screen">
      <Sidebar project={project} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header project={project} />
        <main className="flex-1 overflow-auto">
          <Outlet context={{ project }} />
        </main>
      </div>
    </div>
  )
}

// TypeScript helper for child routes
export function useProjectContext() {
  return useOutletContext<{ project: Project }>()
}
```

---

## Phase 3: Feature Routes Migration (2 weeks)

### 3.1 Migrate Occurrences (Complex Example)

```typescript
// app/routes/projects.$projectId.occurrences.tsx
import { json, type LoaderFunctionArgs, type ActionFunctionArgs } from '@remix-run/node'
import {
  useLoaderData,
  useSearchParams,
  useNavigation,
  Form,
} from '@remix-run/react'
import { requireAuth } from '~/sessions.server'
import { getOccurrences } from '~/services/occurrences.server'
import { OccurrenceGallery } from '~/components/occurrence-gallery'
import { FilterPanel } from '~/components/filter-panel'
import { Pagination } from '~/design-system/components/pagination'

export async function loader({ params, request }: LoaderFunctionArgs) {
  const token = await requireAuth(request)
  const url = new URL(request.url)

  // Extract all filter params from URL
  const filters = {
    taxon: url.searchParams.get('taxon'),
    determination_score__gte: url.searchParams.get('score_min'),
    deployment: url.searchParams.get('deployment'),
    event__start__gte: url.searchParams.get('date_start'),
    event__start__lte: url.searchParams.get('date_end'),
    ordering: url.searchParams.get('ordering') || '-updated_at',
    limit: url.searchParams.get('limit') || '24',
    offset: url.searchParams.get('offset') || '0',
  }

  const data = await getOccurrences(params.projectId!, filters, token)
  return json(data)
}

export default function Occurrences() {
  const data = useLoaderData<typeof loader>()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigation = useNavigation()

  const isLoading = navigation.state === 'loading'

  const updateFilters = (updates: Record<string, string | null>) => {
    setSearchParams((prev) => {
      Object.entries(updates).forEach(([key, value]) => {
        if (value === null || value === '') {
          prev.delete(key)
        } else {
          prev.set(key, value)
        }
      })
      // Reset pagination when filters change
      if (!('offset' in updates)) {
        prev.delete('offset')
      }
      return prev
    })
  }

  const currentPage = Math.floor(
    parseInt(searchParams.get('offset') || '0') /
    parseInt(searchParams.get('limit') || '24')
  ) + 1

  return (
    <div className="p-6">
      <FilterPanel
        currentFilters={Object.fromEntries(searchParams)}
        onFilterChange={updateFilters}
      />

      {isLoading ? (
        <OccurrenceGallerySkeleton />
      ) : (
        <OccurrenceGallery occurrences={data.results} />
      )}

      <Pagination
        total={data.count}
        currentPage={currentPage}
        perPage={parseInt(searchParams.get('limit') || '24')}
        onPageChange={(page) => {
          const offset = (page - 1) * parseInt(searchParams.get('limit') || '24')
          updateFilters({ offset: String(offset) })
        }}
      />
    </div>
  )
}
```

### 3.2 Migrate Occurrence Detail with Actions

```typescript
// app/routes/projects.$projectId.occurrences.$id.tsx
import { json, type LoaderFunctionArgs, type ActionFunctionArgs } from '@remix-run/node'
import { useLoaderData, useNavigation, Form } from '@remix-run/react'
import { requireAuth } from '~/sessions.server'
import {
  getOccurrence,
  createIdentification,
  agreeWithPrediction,
} from '~/services/occurrences.server'
import { OccurrenceDetail } from '~/components/occurrence-detail'
import { IdentificationPanel } from '~/components/identification-panel'
import { TaxonAutocomplete } from '~/components/taxon-autocomplete'

export async function loader({ params, request }: LoaderFunctionArgs) {
  const token = await requireAuth(request)
  const occurrence = await getOccurrence(params.id!, token)
  return json({ occurrence })
}

export async function action({ params, request }: ActionFunctionArgs) {
  const token = await requireAuth(request)
  const formData = await request.formData()
  const intent = formData.get('intent')

  switch (intent) {
    case 'agree': {
      const predictionId = formData.get('predictionId') as string
      await agreeWithPrediction(params.id!, predictionId, token)
      return json({ success: true, action: 'agree' })
    }

    case 'suggest': {
      const taxonId = formData.get('taxonId') as string
      await createIdentification(params.id!, taxonId, token)
      return json({ success: true, action: 'suggest' })
    }

    default:
      return json({ error: 'Unknown action' }, { status: 400 })
  }
}

export default function OccurrenceDetailPage() {
  const { occurrence } = useLoaderData<typeof loader>()
  const navigation = useNavigation()

  const isSubmitting = navigation.state === 'submitting'
  const submittingIntent = navigation.formData?.get('intent')

  return (
    <div className="flex gap-6 p-6">
      <div className="flex-1">
        <OccurrenceDetail occurrence={occurrence} />
      </div>

      <div className="w-80 space-y-4">
        {/* ML Predictions */}
        <div className="border rounded p-4">
          <h3 className="font-semibold mb-3">ML Predictions</h3>
          {occurrence.top_classification && (
            <div className="flex justify-between items-center">
              <span>{occurrence.top_classification.taxon.name}</span>
              <Form method="post">
                <input type="hidden" name="intent" value="agree" />
                <input
                  type="hidden"
                  name="predictionId"
                  value={occurrence.top_classification.id}
                />
                <button
                  type="submit"
                  disabled={isSubmitting && submittingIntent === 'agree'}
                  className="bg-green-600 text-white px-3 py-1 rounded text-sm"
                >
                  {isSubmitting && submittingIntent === 'agree'
                    ? 'Agreeing...'
                    : 'Agree'}
                </button>
              </Form>
            </div>
          )}
        </div>

        {/* Suggest ID */}
        <div className="border rounded p-4">
          <h3 className="font-semibold mb-3">Suggest Identification</h3>
          <Form method="post" className="space-y-3">
            <input type="hidden" name="intent" value="suggest" />
            <TaxonAutocomplete name="taxonId" />
            <button
              type="submit"
              disabled={isSubmitting && submittingIntent === 'suggest'}
              className="w-full bg-blue-600 text-white py-2 rounded"
            >
              {isSubmitting && submittingIntent === 'suggest'
                ? 'Submitting...'
                : 'Submit ID'}
            </button>
          </Form>
        </div>
      </div>
    </div>
  )
}
```

### 3.3 Migration Order for Remaining Routes

| Priority | Route | Complexity | Notes |
|----------|-------|------------|-------|
| 1 | auth.logout | Low | Simple action |
| 2 | projects.new | Low | Form + action |
| 3 | projects.$id.summary | Low | Dashboard display |
| 4 | projects.$id.deployments | Medium | List + CRUD |
| 5 | projects.$id.jobs | Medium | List + actions |
| 6 | projects.$id.jobs.$id | Medium | Progress display |
| 7 | projects.$id.captures | Medium | Gallery + upload |
| 8 | projects.$id.sessions | Medium | Timeline view |
| 9 | projects.$id.taxa | Medium | Tree navigation |
| 10 | projects.$id.settings.* | Low | Settings forms |

---

## Phase 4: Component Migration (1 week)

### 4.1 Move Reusable Components

```bash
# Move design system (no changes needed)
mv src/design-system app/design-system

# Move shared components
mv src/components app/components

# Move domain models
mv src/data-services/models app/models
```

### 4.2 Handle Client-Only Components

```typescript
// app/components/location-map.tsx
// Leaflet must be client-only

import { lazy, Suspense } from 'react'

// Lazy load to avoid SSR
const LeafletMap = lazy(() => import('./leaflet-map.client'))

export function LocationMap(props: LocationMapProps) {
  return (
    <Suspense fallback={<div className="h-64 bg-gray-100 animate-pulse" />}>
      <LeafletMap {...props} />
    </Suspense>
  )
}

// app/components/leaflet-map.client.tsx
// This file only runs on client
import { MapContainer, TileLayer, Marker } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

export default function LeafletMap({ lat, lng, onLocationChange }) {
  return (
    <MapContainer center={[lat, lng]} zoom={13}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <Marker position={[lat, lng]} draggable onDragEnd={onLocationChange} />
    </MapContainer>
  )
}
```

### 4.3 Update Import Paths

Search and replace across codebase:
```
from: '@/components/'  → to: '~/components/'
from: '@/design-system/' → to: '~/design-system/'
from: '@/utils/' → to: '~/utils/'
```

---

## Phase 5: Testing & Validation (1 week)

### 5.1 Run Both Versions

```bash
# Terminal 1: Old Vite version
npm run dev:old  # Port 3000

# Terminal 2: New Remix version
npm run dev      # Port 3001
```

### 5.2 Feature Parity Checklist

For each route, verify:
- [ ] Data loads correctly
- [ ] Forms submit and validate
- [ ] Errors display properly
- [ ] Navigation works
- [ ] URL params work
- [ ] Loading states show
- [ ] Back/forward buttons work

### 5.3 Remove Old Code

Once verified:
```bash
rm -rf src/pages
rm -rf src/data-services/hooks
rm src/app.tsx
rm src/index.tsx
```

---

## Phase 6: Deployment (2-3 days)

### 6.1 Update Docker Configuration

```dockerfile
# Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app
COPY --from=builder /app/build ./build
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./

RUN npm ci --production

ENV NODE_ENV=production
EXPOSE 3000

CMD ["npm", "start"]
```

### 6.2 Update docker-compose.yml

```yaml
services:
  ui:
    build:
      context: ./ui
      dockerfile: Dockerfile
    ports:
      - "4000:3000"
    environment:
      - API_URL=http://django:8000
      - SESSION_SECRET=${SESSION_SECRET}
    depends_on:
      - django
```

### 6.3 Environment Variables

```bash
# .env
API_URL=http://django:8000
SESSION_SECRET=your-secret-key-here  # Generate secure secret
NODE_ENV=production
```

---

## Timeline Summary

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 0: Preparation | 1-2 days | 2 days |
| Phase 1: Parallel Setup | 2-3 days | 5 days |
| Phase 2: Core Routes | 5 days | 2 weeks |
| Phase 3: Feature Routes | 10 days | 4 weeks |
| Phase 4: Components | 5 days | 5 weeks |
| Phase 5: Testing | 5 days | 6 weeks |
| Phase 6: Deployment | 2-3 days | ~6.5 weeks |

**Total: ~6-7 weeks** (slightly faster than Next.js due to simpler patterns)

---

## Rollback Plan

1. Keep `main` branch unchanged
2. Maintain old Vite config in parallel
3. Docker compose can switch:
   ```yaml
   ui:
     # For rollback, switch build context
     build: ./ui-vite  # or ./ui-remix
   ```
4. DNS/proxy can route to old version if needed
