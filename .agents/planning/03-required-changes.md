# Everything That Needs to Change

## Overview

This document catalogs all changes required to migrate from the current Vite + React Router stack to Next.js App Router. Changes are categorized by scope and complexity.

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
├── tailwind.config.js
└── package.json
```

**Next.js Structure:**
```
ui/
├── app/                    # App Router pages
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Home page
│   ├── auth/
│   │   ├── login/page.tsx
│   │   └── reset-password/page.tsx
│   ├── projects/
│   │   ├── page.tsx
│   │   └── [projectId]/
│   │       ├── layout.tsx
│   │       ├── page.tsx
│   │       ├── occurrences/
│   │       │   ├── page.tsx
│   │       │   ├── loading.tsx
│   │       │   └── [id]/page.tsx
│   │       └── ...
│   └── api/                # Route handlers (optional BFF)
├── components/             # Shared components
├── design-system/          # UI primitives (unchanged)
├── data-services/          # API hooks (modified)
├── utils/                  # Utilities (modified)
├── next.config.js
├── tailwind.config.js
└── package.json
```

### Files to Delete
- `vite.config.ts`
- `vite-env.d.ts`
- `src/index.tsx` (replaced by `app/layout.tsx`)
- `src/app.tsx` (router config moves to file system)

### Files to Create
- `next.config.js`
- `middleware.ts` (for auth protection)
- `app/layout.tsx` (root layout with providers)
- `app/*/page.tsx` (for each route)
- `app/*/layout.tsx` (for nested layouts)
- `app/*/loading.tsx` (loading states)
- `app/*/error.tsx` (error boundaries)

---

## 2. Routing Changes

### Route Mapping

| Current Route | Next.js Path |
|---------------|--------------|
| `/` | `app/page.tsx` |
| `/auth/login` | `app/auth/login/page.tsx` |
| `/auth/reset-password` | `app/auth/reset-password/page.tsx` |
| `/auth/reset-password-confirm` | `app/auth/reset-password-confirm/page.tsx` |
| `/projects` | `app/projects/page.tsx` |
| `/projects/:projectId` | `app/projects/[projectId]/page.tsx` |
| `/projects/:projectId/summary` | `app/projects/[projectId]/summary/page.tsx` |
| `/projects/:projectId/occurrences` | `app/projects/[projectId]/occurrences/page.tsx` |
| `/projects/:projectId/occurrences/:id` | `app/projects/[projectId]/occurrences/[id]/page.tsx` |
| `/terms-of-service` | `app/terms-of-service/page.tsx` |

### Layout Changes

**Current** (React Router Outlet):
```tsx
// Project layout with outlet
<ProjectLayout>
  <Outlet context={{ project }} />
</ProjectLayout>
```

**Next.js** (Nested Layouts):
```tsx
// app/projects/[projectId]/layout.tsx
export default function ProjectLayout({ children, params }) {
  return (
    <ProjectProvider projectId={params.projectId}>
      <Sidebar />
      <main>{children}</main>
    </ProjectProvider>
  )
}
```

### Navigation Changes

**Current** (React Router):
```tsx
import { useNavigate, Link, useParams } from 'react-router-dom'

const navigate = useNavigate()
navigate('/projects/123/occurrences')

<Link to={`/projects/${projectId}/occurrences`}>
```

**Next.js**:
```tsx
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'

const router = useRouter()
router.push('/projects/123/occurrences')

<Link href={`/projects/${projectId}/occurrences`}>
```

### Route Constants

**Current** (`utils/constants.ts`):
```typescript
export const STRING = {
  PROJECTS: '/projects',
  OCCURRENCES: (projectId: string) => `/projects/${projectId}/occurrences`,
}
```

**Next.js** (can keep similar pattern or use type-safe routes):
```typescript
// Consider using next-safe-navigation or similar
export const routes = {
  projects: () => '/projects',
  occurrences: (projectId: string) => `/projects/${projectId}/occurrences`,
} as const
```

---

## 3. Data Fetching Changes

### Server Components (New Pattern)

**Pages with initial data fetch:**
```tsx
// app/projects/[projectId]/occurrences/page.tsx
import { cookies } from 'next/headers'

async function getOccurrences(projectId: string) {
  const token = cookies().get('auth_token')?.value
  const res = await fetch(`${API_URL}/occurrences/?project=${projectId}`, {
    headers: { Authorization: `Token ${token}` },
    next: { revalidate: 60 }, // Cache for 60 seconds
  })
  return res.json()
}

export default async function OccurrencesPage({ params }) {
  const data = await getOccurrences(params.projectId)
  return <OccurrencesClient initialData={data} />
}
```

### Client Components (Modified Pattern)

**Current:**
```tsx
export const Occurrences = () => {
  const { occurrences, isLoading } = useOccurrences(params)
  if (isLoading) return <Spinner />
  return <OccurrenceTable data={occurrences} />
}
```

**Next.js:**
```tsx
'use client'

export function OccurrencesClient({ initialData }) {
  const { data } = useOccurrences({
    initialData,  // Hydrate from server
    refetchOnMount: false,
  })
  return <OccurrenceTable data={data} />
}
```

### React Query Configuration

**Current** (`index.tsx`):
```tsx
const queryClient = new QueryClient()

<QueryClientProvider client={queryClient}>
  <App />
</QueryClientProvider>
```

**Next.js** (`app/providers.tsx`):
```tsx
'use client'

export function Providers({ children }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
        refetchOnWindowFocus: false,
      },
    },
  }))

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
```

---

## 4. Authentication Changes

### Token Storage

**Current**: localStorage only

**Next.js**: Cookies (for SSR access) + localStorage fallback

```typescript
// middleware.ts
export function middleware(request: NextRequest) {
  const token = request.cookies.get('auth_token')

  if (!token && isProtectedRoute(request.nextUrl.pathname)) {
    return NextResponse.redirect(new URL('/auth/login', request.url))
  }
}

export const config = {
  matcher: ['/projects/:path*'],
}
```

### Auth Context Changes

**Current:**
```tsx
const setToken = (token: string) => {
  localStorage.setItem('AUTH_TOKEN', token)
  setUser({ loggedIn: true, token })
}
```

**Next.js:**
```tsx
const setToken = async (token: string) => {
  // Set cookie for SSR
  document.cookie = `auth_token=${token}; path=/; max-age=2592000`
  // Also keep in localStorage for client-side access
  localStorage.setItem('AUTH_TOKEN', token)
  setUser({ loggedIn: true, token })
}
```

---

## 5. Component Changes

### 'use client' Directive

Components that need client-side features must be marked:

**Components requiring 'use client':**
- All components using `useState`, `useEffect`, `useContext`
- Components with event handlers (onClick, onChange, etc.)
- Components using browser APIs (localStorage, window)
- Components using React Query hooks
- Components using react-hook-form
- Interactive UI components (dialogs, dropdowns, forms)

**Components that can be Server Components:**
- Static display components
- Layout wrappers
- Components that only receive props

### Component Audit (Sample)

| Component | Client/Server | Reason |
|-----------|--------------|--------|
| `Header` | Client | useState, navigation |
| `Sidebar` | Client | useState, context |
| `OccurrenceTable` | Client | useQuery, onClick |
| `OccurrenceRow` | Server | Just displays props |
| `ProjectLayout` | Server | Layout wrapper |
| `Gallery` | Client | useState, event handlers |
| `Dialog` | Client | Radix UI (interactive) |
| `Button` | Client | onClick handler |
| `StatusBadge` | Server | Static display |

---

## 6. Styling Changes

### Tailwind Configuration

**Changes needed:**
```javascript
// tailwind.config.js
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',     // Add app directory
    './components/**/*.{js,ts,jsx,tsx}',
    './design-system/**/*.{js,ts,jsx,tsx}',
    // Remove src/pages, src/components paths
  ],
}
```

### CSS Imports

**Current** (`index.css`):
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**Next.js** (`app/globals.css`):
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Same custom styles */
```

Import in root layout:
```tsx
// app/layout.tsx
import './globals.css'
```

---

## 7. Image Handling

### Current Image Usage

```tsx
<img src={occurrence.thumbnail} alt={occurrence.name} />
```

### Next.js Image Component

```tsx
import Image from 'next/image'

<Image
  src={occurrence.thumbnail}
  alt={occurrence.name}
  width={200}
  height={200}
  placeholder="blur"
  blurDataURL={occurrence.blurHash}
/>
```

### Remote Image Configuration

```javascript
// next.config.js
module.exports = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'minio',  // MinIO storage
      },
      {
        protocol: 'http',
        hostname: 'localhost',
      },
    ],
  },
}
```

---

## 8. Environment Variables

### Rename Variables

| Current | Next.js |
|---------|---------|
| `VITE_DOCS_URL` | `NEXT_PUBLIC_DOCS_URL` |
| `API_PROXY_TARGET` | Server-side config in `next.config.js` |

### next.config.js Rewrites

```javascript
// next.config.js
module.exports = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.API_URL || 'http://localhost:8000'}/api/:path*`,
      },
      {
        source: '/media/:path*',
        destination: `${process.env.API_URL || 'http://localhost:8000'}/media/:path*`,
      },
    ]
  },
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
  "vite-plugin-eslint": "^1.8.1",
  "react-router-dom": "^6.8.2",
  "react-helmet-async": "^2.0.5"
}
```

### Add
```json
{
  "next": "^14.2.0",
  "@next/bundle-analyzer": "^14.2.0"
}
```

### Update
```json
{
  "@sentry/react": "→ @sentry/nextjs"
}
```

---

## 10. TypeScript Changes

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [
      { "name": "next" }
    ],
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

---

## 11. Testing Changes

### Jest Configuration

```javascript
// jest.config.js
const nextJest = require('next/jest')

const createJestConfig = nextJest({
  dir: './',
})

const customJestConfig = {
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jest-environment-jsdom',
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
}

module.exports = createJestConfig(customJestConfig)
```

### Test Updates

- Update imports for Next.js components
- Mock `next/navigation` instead of `react-router-dom`
- Use `@testing-library/react` with Next.js utilities

---

## Change Summary by Effort

### Low Effort (Configuration)
- [ ] Create next.config.js
- [ ] Update tailwind.config.js content paths
- [ ] Update tsconfig.json
- [ ] Rename environment variables
- [ ] Update package.json dependencies

### Medium Effort (Structural)
- [ ] Create app directory structure
- [ ] Move pages to app/*/page.tsx format
- [ ] Create layout.tsx files
- [ ] Add 'use client' directives
- [ ] Update imports (Link, useRouter, etc.)

### High Effort (Architectural)
- [ ] Implement server components for data fetching
- [ ] Update authentication to use cookies
- [ ] Create middleware for auth protection
- [ ] Modify React Query for SSR hydration
- [ ] Update all tests

### Estimated File Changes
- **New files**: ~50 (layouts, pages, configs)
- **Modified files**: ~100 (components with imports/directives)
- **Deleted files**: ~10 (Vite config, old entry points)
