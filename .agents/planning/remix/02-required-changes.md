# Everything That Needs to Change (Remix)

## Overview

This document catalogs changes required to migrate from Vite + React Router to Remix. Many changes are similar to Next.js, but Remix has its own conventions.

---

## 1. Project Structure

### Directory Reorganization

**Current Structure:**
```
ui/
├── src/
│   ├── index.tsx           # Entry point
│   ├── app.tsx             # Router configuration
│   ├── pages/              # Page components
│   ├── components/         # Shared components
│   ├── design-system/      # UI primitives
│   ├── data-services/      # API hooks
│   └── utils/              # Utilities
├── vite.config.ts
└── package.json
```

**Remix Structure:**
```
ui/
├── app/
│   ├── root.tsx            # Root layout (html, head, body)
│   ├── entry.client.tsx    # Client entry
│   ├── entry.server.tsx    # Server entry
│   ├── routes/             # File-based routes
│   │   ├── _index.tsx      # / (home)
│   │   ├── auth.login.tsx  # /auth/login
│   │   ├── projects._index.tsx         # /projects
│   │   ├── projects.$projectId.tsx     # /projects/:id (layout)
│   │   ├── projects.$projectId._index.tsx  # /projects/:id (index)
│   │   ├── projects.$projectId.occurrences.tsx
│   │   ├── projects.$projectId.occurrences.$id.tsx
│   │   └── ...
│   ├── components/         # Shared components
│   ├── design-system/      # UI primitives (move from src/)
│   ├── models/             # Domain models (from data-services/)
│   ├── services/           # API service functions
│   └── utils/              # Utilities
├── public/                 # Static assets
├── remix.config.js         # Remix configuration
├── tailwind.config.js
└── package.json
```

### Route File Naming Convention

Remix uses dots (`.`) for nesting and `$` for params:

| URL | Remix File |
|-----|------------|
| `/` | `routes/_index.tsx` |
| `/auth/login` | `routes/auth.login.tsx` |
| `/projects` | `routes/projects._index.tsx` |
| `/projects/:id` | `routes/projects.$projectId.tsx` (layout) |
| `/projects/:id` (content) | `routes/projects.$projectId._index.tsx` |
| `/projects/:id/occurrences` | `routes/projects.$projectId.occurrences.tsx` |
| `/projects/:id/occurrences/:occId` | `routes/projects.$projectId.occurrences.$id.tsx` |

### Files to Delete
- `vite.config.ts`
- `vite-env.d.ts`
- `src/index.tsx`
- `src/app.tsx` (router config)
- Most files in `data-services/hooks/` (replaced by loaders/actions)

### Files to Create
- `remix.config.js`
- `app/root.tsx`
- `app/entry.client.tsx`
- `app/entry.server.tsx`
- `app/routes/*.tsx` (for each route)
- `app/services/*.server.ts` (API functions)
- `app/sessions.server.ts` (auth session handling)

---

## 2. Route Migration

### Route Mapping

| Current Route | Remix File | Notes |
|---------------|------------|-------|
| `/` | `routes/_index.tsx` | |
| `/auth/login` | `routes/auth.login.tsx` | |
| `/auth/reset-password` | `routes/auth.reset-password.tsx` | |
| `/projects` | `routes/projects._index.tsx` | |
| `/projects/:projectId` | `routes/projects.$projectId.tsx` | Layout wrapper |
| `/projects/:projectId/summary` | `routes/projects.$projectId.summary.tsx` | |
| `/projects/:projectId/occurrences` | `routes/projects.$projectId.occurrences.tsx` | |
| `/projects/:projectId/occurrences/:id` | `routes/projects.$projectId.occurrences.$id.tsx` | |
| `/projects/:projectId/jobs` | `routes/projects.$projectId.jobs.tsx` | |
| `/projects/:projectId/jobs/:id` | `routes/projects.$projectId.jobs.$id.tsx` | |

### Layout Routes

**Current** (React Router Outlet):
```tsx
// Separate file for layout
<ProjectLayout>
  <Outlet context={{ project }} />
</ProjectLayout>
```

**Remix** (Pathless layout routes):
```tsx
// routes/projects.$projectId.tsx - Layout route
import { Outlet, useLoaderData } from '@remix-run/react'

export async function loader({ params }: LoaderFunctionArgs) {
  const project = await getProject(params.projectId)
  if (!project) throw new Response('Not Found', { status: 404 })
  return json({ project })
}

export default function ProjectLayout() {
  const { project } = useLoaderData<typeof loader>()

  return (
    <div className="flex">
      <Sidebar project={project} />
      <main className="flex-1">
        <Outlet context={{ project }} />
      </main>
    </div>
  )
}
```

---

## 3. Data Fetching Migration

### Replace React Query Hooks with Loaders

**Before** (React Query):
```typescript
// data-services/hooks/occurrences/useOccurrences.ts
export function useOccurrences(params?: FetchParams) {
  const { user } = useUser()
  const fetchUrl = getFetchUrl({ collection: 'occurrences', params })

  return useQuery({
    queryKey: ['occurrences', params],
    queryFn: async () => {
      const response = await axios.get(fetchUrl, {
        headers: getAuthHeader(user),
      })
      return response.data
    },
  })
}

// In component
function Occurrences() {
  const { data, isLoading, error } = useOccurrences(params)
  if (isLoading) return <Spinner />
  if (error) return <Error error={error} />
  return <OccurrenceList data={data.results} />
}
```

**After** (Remix Loader):
```typescript
// routes/projects.$projectId.occurrences.tsx
import { json, type LoaderFunctionArgs } from '@remix-run/node'
import { useLoaderData } from '@remix-run/react'
import { requireAuth } from '~/services/auth.server'
import { getOccurrences } from '~/services/occurrences.server'

export async function loader({ params, request }: LoaderFunctionArgs) {
  const token = await requireAuth(request)
  const url = new URL(request.url)

  // Filters from URL search params
  const filters = {
    taxon: url.searchParams.get('taxon'),
    score_min: url.searchParams.get('score_min'),
    page: url.searchParams.get('page') || '1',
    ordering: url.searchParams.get('ordering') || '-updated_at',
  }

  const data = await getOccurrences(params.projectId!, filters, token)
  return json(data)
}

export default function Occurrences() {
  const data = useLoaderData<typeof loader>()
  // No loading state needed - Remix handles it
  return <OccurrenceList data={data.results} total={data.count} />
}
```

### Service Functions (Server-Side)

```typescript
// app/services/occurrences.server.ts
const API_URL = process.env.API_URL || 'http://localhost:8000'

export async function getOccurrences(
  projectId: string,
  filters: Record<string, string | null>,
  token: string
) {
  const params = new URLSearchParams()
  params.set('project', projectId)

  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value)
  })

  const response = await fetch(
    `${API_URL}/api/v2/occurrences/?${params}`,
    {
      headers: {
        Authorization: `Token ${token}`,
        'Content-Type': 'application/json',
      },
    }
  )

  if (!response.ok) {
    throw new Response('Failed to fetch occurrences', {
      status: response.status,
    })
  }

  return response.json()
}
```

---

## 4. Mutation Migration

### Replace useMutation with Actions

**Before** (React Query):
```typescript
// hooks/useCreateIdentification.ts
export function useCreateIdentification(onSuccess?: () => void) {
  const { user } = useUser()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: IdentificationInput) => {
      const response = await axios.post(
        '/api/v2/identifications/',
        data,
        { headers: getAuthHeader(user) }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['identifications'])
      queryClient.invalidateQueries(['occurrences'])
      onSuccess?.()
    },
  })
}

// In component
const { mutate, isLoading } = useCreateIdentification(() => setOpen(false))

<form onSubmit={(e) => {
  e.preventDefault()
  mutate({ occurrence_id: occurrenceId, taxon_id: selectedTaxon })
}}>
```

**After** (Remix Action):
```typescript
// routes/projects.$projectId.occurrences.$id.tsx
import { json, redirect, type ActionFunctionArgs } from '@remix-run/node'
import { Form, useNavigation } from '@remix-run/react'
import { requireAuth } from '~/services/auth.server'
import { createIdentification, agreeWithPrediction } from '~/services/identifications.server'

export async function action({ params, request }: ActionFunctionArgs) {
  const token = await requireAuth(request)
  const formData = await request.formData()
  const intent = formData.get('intent')

  switch (intent) {
    case 'create-identification': {
      const taxonId = formData.get('taxonId') as string
      await createIdentification({
        occurrenceId: params.id!,
        taxonId,
        token,
      })
      // Remix automatically revalidates loaders after action
      return json({ success: true })
    }

    case 'agree': {
      const predictionId = formData.get('predictionId') as string
      await agreeWithPrediction({
        occurrenceId: params.id!,
        predictionId,
        token,
      })
      return json({ success: true })
    }

    default:
      return json({ error: 'Unknown action' }, { status: 400 })
  }
}

export default function OccurrenceDetail() {
  const navigation = useNavigation()
  const isSubmitting = navigation.state === 'submitting'

  return (
    <>
      {/* Agree button */}
      <Form method="post">
        <input type="hidden" name="intent" value="agree" />
        <input type="hidden" name="predictionId" value={prediction.id} />
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Agreeing...' : 'Agree'}
        </button>
      </Form>

      {/* Suggest ID form */}
      <Form method="post">
        <input type="hidden" name="intent" value="create-identification" />
        <TaxonAutocomplete name="taxonId" />
        <button type="submit" disabled={isSubmitting}>
          Submit ID
        </button>
      </Form>
    </>
  )
}
```

---

## 5. Authentication Migration

### Session-Based Auth

**Create session utility:**
```typescript
// app/sessions.server.ts
import { createCookieSessionStorage, redirect } from '@remix-run/node'

const sessionStorage = createCookieSessionStorage({
  cookie: {
    name: '__session',
    httpOnly: true,
    path: '/',
    sameSite: 'lax',
    secrets: [process.env.SESSION_SECRET!],
    secure: process.env.NODE_ENV === 'production',
  },
})

export async function getSession(request: Request) {
  return sessionStorage.getSession(request.headers.get('Cookie'))
}

export async function createUserSession(token: string, redirectTo: string) {
  const session = await sessionStorage.getSession()
  session.set('token', token)
  return redirect(redirectTo, {
    headers: {
      'Set-Cookie': await sessionStorage.commitSession(session),
    },
  })
}

export async function requireAuth(request: Request) {
  const session = await getSession(request)
  const token = session.get('token')
  if (!token) {
    throw redirect('/auth/login')
  }
  return token
}

export async function logout(request: Request) {
  const session = await getSession(request)
  return redirect('/auth/login', {
    headers: {
      'Set-Cookie': await sessionStorage.destroySession(session),
    },
  })
}
```

**Login route:**
```typescript
// routes/auth.login.tsx
import { json, redirect, type ActionFunctionArgs } from '@remix-run/node'
import { Form, useActionData, useNavigation } from '@remix-run/react'
import { createUserSession } from '~/sessions.server'

export async function action({ request }: ActionFunctionArgs) {
  const formData = await request.formData()
  const email = formData.get('email') as string
  const password = formData.get('password') as string

  // Validate
  const errors: Record<string, string> = {}
  if (!email) errors.email = 'Email is required'
  if (!password) errors.password = 'Password is required'
  if (Object.keys(errors).length) {
    return json({ errors }, { status: 400 })
  }

  // Authenticate with Django
  const response = await fetch(`${process.env.API_URL}/api/v2/auth/token/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!response.ok) {
    return json({ errors: { form: 'Invalid credentials' } }, { status: 401 })
  }

  const { auth_token } = await response.json()
  return createUserSession(auth_token, '/projects')
}

export default function Login() {
  const actionData = useActionData<typeof action>()
  const navigation = useNavigation()
  const isSubmitting = navigation.state === 'submitting'

  return (
    <Form method="post" className="space-y-4">
      {actionData?.errors?.form && (
        <div className="text-red-500">{actionData.errors.form}</div>
      )}

      <div>
        <label htmlFor="email">Email</label>
        <input
          type="email"
          name="email"
          id="email"
          required
        />
        {actionData?.errors?.email && (
          <span className="text-red-500">{actionData.errors.email}</span>
        )}
      </div>

      <div>
        <label htmlFor="password">Password</label>
        <input
          type="password"
          name="password"
          id="password"
          required
        />
      </div>

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Logging in...' : 'Log in'}
      </button>
    </Form>
  )
}
```

---

## 6. Navigation Migration

### Link and Navigation Changes

**Before** (React Router):
```typescript
import { Link, useNavigate, useParams, useLocation } from 'react-router-dom'

const navigate = useNavigate()
const { projectId } = useParams()
const location = useLocation()

navigate(`/projects/${projectId}/occurrences`)
<Link to="/projects">Projects</Link>
```

**After** (Remix):
```typescript
import { Link, useNavigate, useParams, useLocation } from '@remix-run/react'

const navigate = useNavigate()
const { projectId } = useParams()
const location = useLocation()

navigate(`/projects/${projectId}/occurrences`)
<Link to="/projects">Projects</Link>

// Prefetching (Remix bonus)
<Link to="/projects" prefetch="intent">Projects</Link>
```

Navigation APIs are nearly identical (Remix is built on React Router).

---

## 7. Loading States

### Pending UI with useNavigation

**Global loading indicator:**
```typescript
// app/root.tsx
import { useNavigation } from '@remix-run/react'

export default function App() {
  const navigation = useNavigation()
  const isLoading = navigation.state === 'loading'

  return (
    <html>
      <head>
        <Meta />
        <Links />
      </head>
      <body>
        {isLoading && <GlobalLoadingBar />}
        <Outlet />
        <Scripts />
      </body>
    </html>
  )
}
```

**Route-specific loading:**
```typescript
// routes/projects.$projectId.occurrences.tsx
export default function Occurrences() {
  const navigation = useNavigation()
  const isLoadingNewData =
    navigation.state === 'loading' &&
    navigation.location.pathname.includes('occurrences')

  return (
    <div>
      <FilterPanel />
      {isLoadingNewData ? (
        <OccurrenceListSkeleton />
      ) : (
        <OccurrenceList data={data} />
      )}
    </div>
  )
}
```

---

## 8. URL Search Params (Filters)

### useSearchParams for Filter State

```typescript
// routes/projects.$projectId.occurrences.tsx
import { useSearchParams, useLoaderData } from '@remix-run/react'

export default function Occurrences() {
  const data = useLoaderData<typeof loader>()
  const [searchParams, setSearchParams] = useSearchParams()

  const currentTaxon = searchParams.get('taxon') || ''
  const currentScore = searchParams.get('score_min') || ''

  const updateFilter = (key: string, value: string) => {
    setSearchParams(prev => {
      if (value) {
        prev.set(key, value)
      } else {
        prev.delete(key)
      }
      prev.delete('page') // Reset pagination
      return prev
    })
    // Remix automatically re-runs loader with new URL
  }

  return (
    <div>
      <FilterPanel
        taxon={currentTaxon}
        score={currentScore}
        onTaxonChange={(v) => updateFilter('taxon', v)}
        onScoreChange={(v) => updateFilter('score_min', v)}
      />
      <OccurrenceList data={data.results} />
      <Pagination
        total={data.count}
        currentPage={parseInt(searchParams.get('page') || '1')}
        onPageChange={(p) => updateFilter('page', String(p))}
      />
    </div>
  )
}
```

---

## 9. Package Changes

### Remove
```json
{
  "vite": "^4.5.3",
  "@vitejs/plugin-react": "^4.2.0",
  "vite-tsconfig-paths": "^4.2.1",
  "vite-plugin-svgr": "^4.2.0",
  "react-router-dom": "^6.8.2",
  "@tanstack/react-query": "^4.29.5",  // Can remove or keep for complex cases
  "axios": "^1.6.2",  // Replace with native fetch
  "react-helmet-async": "^2.0.5"
}
```

### Add
```json
{
  "@remix-run/node": "^2.x",
  "@remix-run/react": "^2.x",
  "@remix-run/serve": "^2.x",  // Or express adapter
  "isbot": "^4.x"
}
```

### Keep
```json
{
  "react-hook-form": "^7.43.9",  // For complex client validation
  "tailwindcss": "^3.4.14",
  "@radix-ui/*": "...",
  "nova-ui-kit": "^1.1.32",
  "leaflet": "^1.9.3",
  "plotly.js": "^2.25.2",
  "lodash": "^4.17.21",
  "date-fns": "..."
}
```

---

## 10. What Can Be Deleted (Boilerplate Reduction)

### Hooks That Become Unnecessary

| Current Hook | Replaced By |
|--------------|-------------|
| `useOccurrences` | Loader in route file |
| `useOccurrenceDetails` | Loader in route file |
| `useProjects` | Loader in route file |
| `useJobs` | Loader in route file |
| `useCreateJob` | Action in route file |
| `useCreateIdentification` | Action in route file |
| `useLogin` | Action in login route |
| `useLogout` | Action/utility |
| `usePagination` | URL search params |
| `useSort` | URL search params |
| `useFilters` | URL search params |

**Estimated removal**: ~40 hook files → ~25 route files with loaders/actions

### Utility Functions That Simplify

| Current | Replacement |
|---------|-------------|
| `getFetchUrl()` | Native URLSearchParams |
| `getAuthHeader()` | Session-based in services |
| `convertToServerFieldValues()` | FormData in actions |
| Manual cache invalidation | Automatic revalidation |

---

## Change Summary

### Effort Comparison (vs Next.js)

| Category | Next.js Effort | Remix Effort | Notes |
|----------|----------------|--------------|-------|
| Route structure | Medium | Medium | Similar file-based routing |
| Data fetching | High | **Medium** | Loaders are more prescribed |
| Mutations | High | **Low** | Actions replace custom hooks |
| Forms | Medium | **Low** | `<Form>` is built-in |
| Auth | Medium | Medium | Session-based either way |
| URL state | High | **Low** | Built into the model |
| Components | Low | Low | Add 'use client' equivalent |

### Net Boilerplate Change

| Category | Current Files | After Remix | Change |
|----------|---------------|-------------|--------|
| Route config | 1 large file | 0 | -1 |
| Data hooks | ~22 | ~5 (complex only) | -17 |
| Mutation hooks | ~15 | 0 | -15 |
| Filter/sort hooks | ~5 | 0 | -5 |
| Route files | ~25 | ~25 | 0 |
| Service files | 0 | ~10 | +10 |
| **Net** | ~68 | ~40 | **-28 files** |

Plus significant reduction in code within remaining files due to:
- No loading state handling in components
- No manual cache invalidation
- No manual URL synchronization
- Prescribed patterns reduce decision-making
