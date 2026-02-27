# What Remix Can Offer

## Overview

Remix is a full-stack React framework built by the React Router team. It emphasizes web standards, progressive enhancement, and has strong opinions about data flow. It's often described as "the React framework that feels like Rails/Django."

---

## Philosophy Comparison

| Aspect | Next.js | Remix |
|--------|---------|-------|
| Primary focus | Static/SSR optimization | Data flow & web standards |
| Form handling | Basic (Server Actions) | First-class (`<Form>`, actions) |
| Data loading | Flexible (many patterns) | Opinionated (loaders) |
| Mutations | Server Actions (newer) | Actions (mature pattern) |
| Error handling | error.tsx convention | errorElement + boundaries |
| Mental model | "Pages with data" | "Routes as API endpoints" |
| Progressive enhancement | Optional | Core principle |

---

## What Remix Provides (vs Current Stack)

### 1. Loaders: Prescribed Data Loading

**Current Pattern** (React Query):
```typescript
// Multiple files, manual wiring
// hooks/occurrences/useOccurrences.ts
export function useOccurrences(params) {
  return useQuery({
    queryKey: ['occurrences', params],
    queryFn: () => fetchOccurrences(params),
  })
}

// pages/occurrences/occurrences.tsx
export function Occurrences() {
  const { data, isLoading, error } = useOccurrences(params)
  if (isLoading) return <Spinner />
  if (error) return <Error />
  return <OccurrenceList data={data} />
}
```

**Remix Pattern** (Loaders):
```typescript
// routes/projects.$projectId.occurrences.tsx
// ONE file, prescribed pattern

// Data loading - runs on server
export async function loader({ params, request }: LoaderFunctionArgs) {
  const token = await getAuthToken(request)
  const url = new URL(request.url)
  const filters = Object.fromEntries(url.searchParams)

  const occurrences = await fetchOccurrences(params.projectId, filters, token)
  return json({ occurrences })
}

// Component - receives data, never loading state
export default function Occurrences() {
  const { occurrences } = useLoaderData<typeof loader>()
  return <OccurrenceList data={occurrences} />
}
```

**Benefits**:
- Data fetching has ONE prescribed location (loader)
- Component never sees loading state (Remix handles it)
- Type safety between loader and component
- Automatic request deduplication
- Parallel data loading for nested routes

### 2. Actions: Prescribed Mutation Handling

**Current Pattern** (React Query mutations):
```typescript
// hooks/identifications/useCreateIdentification.ts
export function useCreateIdentification(onSuccess) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data) => axios.post('/api/v2/identifications/', data),
    onSuccess: () => {
      queryClient.invalidateQueries(['identifications'])
      queryClient.invalidateQueries(['occurrences'])
      onSuccess?.()
    },
  })
}

// In component
const { mutate, isLoading } = useCreateIdentification(() => closeModal())
<form onSubmit={(e) => { e.preventDefault(); mutate(formData) }}>
```

**Remix Pattern** (Actions):
```typescript
// routes/projects.$projectId.occurrences.$id.tsx

// Mutation handling - runs on server
export async function action({ params, request }: ActionFunctionArgs) {
  const token = await getAuthToken(request)
  const formData = await request.formData()
  const intent = formData.get('intent')

  if (intent === 'create-identification') {
    const taxonId = formData.get('taxonId')
    await createIdentification(params.id, taxonId, token)
    return json({ success: true })
  }

  if (intent === 'agree') {
    await agreeWithPrediction(params.id, token)
    return json({ success: true })
  }

  return json({ error: 'Unknown intent' }, { status: 400 })
}

// In component - use Remix's Form
export default function OccurrenceDetail() {
  const navigation = useNavigation()
  const isSubmitting = navigation.state === 'submitting'

  return (
    <Form method="post">
      <input type="hidden" name="intent" value="agree" />
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Saving...' : 'Agree'}
      </button>
    </Form>
  )
}
```

**Benefits**:
- Mutations have ONE prescribed location (action)
- Form submission is standard HTML (progressive enhancement)
- Automatic revalidation after mutations
- No manual cache invalidation
- Pending states via `useNavigation()`

### 3. Forms: First-Class Support

**Current Pattern**:
```typescript
// Manual preventDefault, manual state, manual submission
const { register, handleSubmit, formState } = useForm()
const { mutate, isLoading } = useCreateJob()

return (
  <form onSubmit={handleSubmit((data) => mutate(data))}>
    <input {...register('name')} />
    <button disabled={isLoading}>
      {isLoading ? 'Creating...' : 'Create'}
    </button>
  </form>
)
```

**Remix Pattern**:
```typescript
// Remix Form component with built-in states
import { Form, useNavigation, useActionData } from '@remix-run/react'

export default function NewJob() {
  const navigation = useNavigation()
  const actionData = useActionData<typeof action>()

  return (
    <Form method="post">
      <input name="name" required />
      {actionData?.errors?.name && (
        <span className="error">{actionData.errors.name}</span>
      )}
      <button type="submit">
        {navigation.state === 'submitting' ? 'Creating...' : 'Create'}
      </button>
    </Form>
  )
}

// Action handles submission and validation
export async function action({ request }: ActionFunctionArgs) {
  const formData = await request.formData()
  const name = formData.get('name')

  if (!name) {
    return json({ errors: { name: 'Name is required' } }, { status: 400 })
  }

  const job = await createJob({ name })
  return redirect(`/jobs/${job.id}`)
}
```

**Benefits**:
- `<Form>` works without JavaScript (progressive enhancement)
- Pending state via `useNavigation()` - ONE pattern
- Validation errors returned from action
- File uploads work naturally with FormData
- Can still use react-hook-form for complex client validation

### 4. File Uploads (Mixed Content Forms)

**Remix handles multipart forms naturally**:

```typescript
// routes/deployments.$id.tsx
export async function action({ request }: ActionFunctionArgs) {
  const formData = await request.formData()

  // Text fields
  const name = formData.get('name') as string
  const description = formData.get('description') as string

  // File upload
  const imageFile = formData.get('image') as File
  if (imageFile && imageFile.size > 0) {
    const buffer = await imageFile.arrayBuffer()
    await uploadToS3(buffer, imageFile.name)
  }

  await updateDeployment({ name, description, imageUrl })
  return redirect('/deployments')
}

// Component
export default function EditDeployment() {
  return (
    <Form method="post" encType="multipart/form-data">
      <input name="name" type="text" />
      <textarea name="description" />
      <input name="image" type="file" accept="image/*" />
      <button type="submit">Save</button>
    </Form>
  )
}
```

**No special libraries needed** - standard FormData API.

### 5. URL State Synchronization

**Current Pattern** (manual sync):
```typescript
// Custom hooks to sync URL params with state
const [filters, setFilters] = useState(() => parseUrlParams())

useEffect(() => {
  updateUrlParams(filters)
}, [filters])
```

**Remix Pattern** (URL is the state):
```typescript
// routes/projects.$projectId.occurrences.tsx
export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url)
  const taxon = url.searchParams.get('taxon')
  const score = url.searchParams.get('score')
  const page = url.searchParams.get('page') || '1'

  // Filters come from URL, loader fetches matching data
  const data = await fetchOccurrences({ taxon, score, page })
  return json(data)
}

export default function Occurrences() {
  const [searchParams, setSearchParams] = useSearchParams()

  const handleFilterChange = (field: string, value: string) => {
    setSearchParams(prev => {
      prev.set(field, value)
      prev.set('page', '1') // Reset pagination
      return prev
    })
    // That's it! Remix automatically re-runs loader
  }
}
```

**Benefits**:
- URL IS the source of truth
- Changing URL params automatically re-fetches data
- No manual synchronization code
- Back/forward buttons work perfectly
- Shareable/bookmarkable filter states

### 6. Nested Routes with Parallel Loading

**Remix loads all nested route data in parallel**:

```
routes/
├── projects.tsx                    # Layout + loader
├── projects.$projectId.tsx         # Project layout + loader
└── projects.$projectId.occurrences.tsx  # Occurrences + loader
```

When visiting `/projects/123/occurrences`:
- All 3 loaders run **in parallel** (not waterfall)
- Each layout renders as its data arrives
- Child routes don't wait for parent data

```typescript
// projects.tsx
export async function loader() {
  return json({ projects: await fetchProjects() })
}

// projects.$projectId.tsx
export async function loader({ params }) {
  return json({ project: await fetchProject(params.projectId) })
}

// projects.$projectId.occurrences.tsx
export async function loader({ params, request }) {
  const filters = getFiltersFromUrl(request.url)
  return json({ occurrences: await fetchOccurrences(params.projectId, filters) })
}
```

### 7. Error Boundaries (Prescribed)

```typescript
// routes/projects.$projectId.occurrences.tsx

export function ErrorBoundary() {
  const error = useRouteError()

  if (isRouteErrorResponse(error)) {
    return (
      <div>
        <h1>{error.status} {error.statusText}</h1>
        <p>{error.data}</p>
      </div>
    )
  }

  return (
    <div>
      <h1>Something went wrong</h1>
      <p>{error instanceof Error ? error.message : 'Unknown error'}</p>
    </div>
  )
}
```

Errors bubble up to nearest ErrorBoundary - no manual setup.

---

## Remix vs Next.js Comparison

| Feature | Next.js | Remix | Winner for Your Needs |
|---------|---------|-------|----------------------|
| File-based routing | ✅ Yes | ✅ Yes | Tie |
| Data loading pattern | Flexible (many ways) | Prescribed (loaders) | **Remix** |
| Mutation pattern | Server Actions | Actions | **Remix** (more mature) |
| Form handling | Basic | First-class | **Remix** |
| File uploads | Manual | Built-in FormData | **Remix** |
| URL state sync | Manual | Built-in | **Remix** |
| Loading states | loading.tsx | useNavigation | Tie |
| Error handling | error.tsx | ErrorBoundary | Tie |
| Progressive enhancement | Optional | Core | Remix (if you care) |
| Community size | Larger | Smaller | Next.js |
| Vercel integration | Native | Good | Next.js |
| Learning resources | More | Less | Next.js |
| Opinions/conventions | Medium | High | **Remix** |

---

## What Remix Does NOT Provide

Still need external solutions for:

| Need | Remix Provides | You Still Need |
|------|---------------|----------------|
| Complex client forms | Basic `<Form>` | react-hook-form for validation |
| Tables with sorting | Nothing | TanStack Table |
| Data grids | Nothing | AG Grid or similar |
| i18n | Nothing built-in | remix-i18next |
| Auth | Nothing built-in | Custom or remix-auth |
| Image optimization | Nothing | CDN or custom |
| Maps | Nothing | Leaflet (same as now) |
| Charts | Nothing | Plotly (same as now) |

---

## Summary: Why Remix Fits Your Motivations

| Your Motivation | How Remix Helps |
|-----------------|-----------------|
| Reduce boilerplate | Loaders/actions replace custom hooks |
| Stop reinventing patterns | Data flow is prescribed |
| Opinionated framework | Very opinionated about data |
| Established places | loader = data, action = mutations |
| Small team leverage | Less custom code to maintain |
| Intern onboarding | "This is how Remix works" (external docs) |
| AI agent compatibility | Standard patterns AI knows |

Remix is closer to the "DRF of frontend" than Next.js because it has **stronger opinions about how data should flow**.
