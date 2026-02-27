# Migration Steps

## Overview

This document outlines a phased approach to migrating the Antenna UI from Vite + React Router to Next.js App Router. The migration is designed to be incremental, allowing the application to remain functional throughout.

---

## Phase 0: Preparation

### 0.1 Create Migration Branch
```bash
git checkout -b feature/nextjs-migration
```

### 0.2 Audit Current Application
- [ ] Document all routes and their data dependencies
- [ ] Identify components using browser APIs (localStorage, window)
- [ ] List all third-party libraries and check Next.js compatibility
- [ ] Note any Vite-specific features in use (import.meta, VITE_ env vars)
- [ ] Review current test coverage

### 0.3 Set Up Development Environment
- [ ] Ensure Node.js 18.17+ is installed
- [ ] Review Docker Compose configuration for Next.js support
- [ ] Plan CI/CD changes

### 0.4 Create Compatibility Checklist

| Library | Status | Action Needed |
|---------|--------|---------------|
| react-query | ✅ | Works with Next.js |
| react-hook-form | ✅ | Works with Next.js |
| tailwindcss | ✅ | Works with Next.js |
| radix-ui | ✅ | Works with Next.js |
| leaflet | ⚠️ | Needs 'use client' |
| plotly | ⚠️ | Needs 'use client' |
| sentry | ⚠️ | Switch to @sentry/nextjs |
| nova-ui-kit | ✅ | Works with Next.js |

---

## Phase 1: Parallel Setup

### 1.1 Initialize Next.js Alongside Vite

Keep existing Vite setup while adding Next.js:

```bash
cd ui

# Install Next.js dependencies
yarn add next@14

# Create Next.js config
touch next.config.js
```

### 1.2 Create next.config.js

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // Preserve existing paths during migration
  experimental: {
    // Enable if needed for gradual migration
  },

  // Proxy API requests to Django (like Vite did)
  async rewrites() {
    const apiUrl = process.env.API_URL || 'http://localhost:8000'
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
      {
        source: '/media/:path*',
        destination: `${apiUrl}/media/:path*`,
      },
    ]
  },

  // Image optimization config
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
      },
      {
        protocol: 'http',
        hostname: 'minio',
      },
      {
        protocol: 'https',
        hostname: '*.insectai.org',
      },
    ],
  },

  // Transpile nova-ui-kit if needed
  transpilePackages: ['nova-ui-kit'],
}

module.exports = nextConfig
```

### 1.3 Update package.json Scripts

```json
{
  "scripts": {
    "dev": "vite",
    "dev:next": "next dev -p 3001",
    "build": "vite build",
    "build:next": "next build",
    "start:next": "next start",
    "lint": "eslint . --ext .ts,.tsx",
    "test": "jest"
  }
}
```

### 1.4 Create App Directory Structure

```bash
mkdir -p app
touch app/layout.tsx
touch app/page.tsx
touch app/globals.css
touch app/providers.tsx
```

### 1.5 Create Root Layout

```typescript
// app/layout.tsx
import type { Metadata } from 'next'
import { Providers } from './providers'
import './globals.css'

export const metadata: Metadata = {
  title: 'Antenna - Insect Monitoring Platform',
  description: 'Automated Monitoring of Insects ML Platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
```

### 1.6 Create Client Providers

```typescript
// app/providers.tsx
'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { useState } from 'react'
import { UserContextProvider } from '@/utils/user/userContext'
import { UserInfoContextProvider } from '@/utils/user/userInfoContext'
import { UserPreferencesContextProvider } from '@/utils/userPreferences/userPreferencesContext'
import { BreadcrumbContextProvider } from '@/utils/breadcrumbContext'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      <UserContextProvider>
        <UserInfoContextProvider>
          <UserPreferencesContextProvider>
            <BreadcrumbContextProvider>
              {children}
            </BreadcrumbContextProvider>
          </UserPreferencesContextProvider>
        </UserInfoContextProvider>
      </UserContextProvider>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
```

### 1.7 Move Global Styles

```css
/* app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Copy from existing src/index.css */
fieldset, li, ul, ol {
  all: unset;
}

a {
  display: inline-block;
  text-decoration: none;
}

/* ... rest of global styles */
```

---

## Phase 2: Core Infrastructure Migration

### 2.1 Update TypeScript Configuration

```json
// tsconfig.json
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
    "plugins": [{ "name": "next" }],
    "baseUrl": ".",
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": [
    "next-env.d.ts",
    "**/*.ts",
    "**/*.tsx",
    ".next/types/**/*.ts"
  ],
  "exclude": ["node_modules"]
}
```

### 2.2 Update Tailwind Configuration

```javascript
// tailwind.config.js
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx}',
    './design-system/**/*.{js,ts,jsx,tsx}',
    './pages/**/*.{js,ts,jsx,tsx}',  // Keep during migration
    './src/**/*.{js,ts,jsx,tsx}',    // Keep during migration
    './node_modules/nova-ui-kit/**/*.{js,ts,jsx,tsx}',
  ],
  // ... rest of config unchanged
}
```

### 2.3 Create Authentication Middleware

```typescript
// middleware.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const token = request.cookies.get('auth_token')?.value
  const { pathname } = request.nextUrl

  // Public routes that don't require auth
  const publicRoutes = [
    '/auth/login',
    '/auth/reset-password',
    '/auth/reset-password-confirm',
    '/terms-of-service',
    '/code-of-conduct',
  ]

  const isPublicRoute = publicRoutes.some(route =>
    pathname.startsWith(route)
  )

  // Redirect to login if accessing protected route without token
  if (!token && !isPublicRoute && pathname !== '/') {
    return NextResponse.redirect(new URL('/auth/login', request.url))
  }

  // Redirect to projects if accessing login while authenticated
  if (token && pathname === '/auth/login') {
    return NextResponse.redirect(new URL('/projects', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico|media).*)',
  ],
}
```

### 2.4 Update Auth Context for Cookies

```typescript
// utils/user/userContext.tsx
'use client'

import { createContext, useContext, useState, useCallback } from 'react'
import Cookies from 'js-cookie'  // Add: yarn add js-cookie @types/js-cookie

const AUTH_TOKEN_KEY = 'auth_token'

interface UserContextType {
  user: { loggedIn: boolean; token?: string }
  setToken: (token: string) => void
  clearToken: () => void
}

export function UserContextProvider({ children }) {
  const [user, setUser] = useState(() => {
    // Check both cookie and localStorage for token
    const cookieToken = Cookies.get(AUTH_TOKEN_KEY)
    const localToken = typeof window !== 'undefined'
      ? localStorage.getItem(AUTH_TOKEN_KEY)
      : null
    const token = cookieToken || localToken
    return { loggedIn: !!token, token }
  })

  const setToken = useCallback((token: string) => {
    // Set cookie for SSR access
    Cookies.set(AUTH_TOKEN_KEY, token, {
      expires: 30,  // 30 days
      path: '/',
      sameSite: 'lax'
    })
    // Also set localStorage for client-side
    localStorage.setItem(AUTH_TOKEN_KEY, token)
    setUser({ loggedIn: true, token })
  }, [])

  const clearToken = useCallback(() => {
    Cookies.remove(AUTH_TOKEN_KEY)
    localStorage.removeItem(AUTH_TOKEN_KEY)
    setUser({ loggedIn: false, token: undefined })
  }, [])

  return (
    <UserContext.Provider value={{ user, setToken, clearToken }}>
      {children}
    </UserContext.Provider>
  )
}
```

---

## Phase 3: Route-by-Route Migration

### Migration Order (by complexity, low to high):

1. **Static pages** (easiest)
2. **Auth pages** (simple forms)
3. **List pages** (projects, deployments)
4. **Detail pages** (with params)
5. **Modal routes** (intercepting routes)
6. **Complex pages** (occurrences with filters)

### 3.1 Migrate Static Pages First

```typescript
// app/terms-of-service/page.tsx
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Terms of Service | Antenna',
}

export default function TermsOfServicePage() {
  return (
    <main>
      {/* Import and render existing component */}
      <TermsOfService />
    </main>
  )
}
```

### 3.2 Migrate Auth Pages

```typescript
// app/auth/login/page.tsx
import { Metadata } from 'next'
import { LoginForm } from '@/pages/auth/login'

export const metadata: Metadata = {
  title: 'Login | Antenna',
}

export default function LoginPage() {
  return <LoginForm />
}
```

Update login component with 'use client':
```typescript
// pages/auth/login.tsx (or move to components/)
'use client'

import { useRouter } from 'next/navigation'  // Changed from react-router-dom
// ... rest of component
```

### 3.3 Migrate Project List

```typescript
// app/projects/page.tsx
import { Metadata } from 'next'
import { cookies } from 'next/headers'
import { ProjectsList } from '@/components/projects/projects-list'

export const metadata: Metadata = {
  title: 'Projects | Antenna',
}

async function getProjects() {
  const token = cookies().get('auth_token')?.value
  const res = await fetch(`${process.env.API_URL}/api/v2/projects/`, {
    headers: { Authorization: `Token ${token}` },
    next: { revalidate: 60 },
  })
  if (!res.ok) return null
  return res.json()
}

export default async function ProjectsPage() {
  const initialData = await getProjects()
  return <ProjectsList initialData={initialData} />
}
```

### 3.4 Create Project Layout

```typescript
// app/projects/[projectId]/layout.tsx
import { cookies } from 'next/headers'
import { ProjectLayoutClient } from '@/components/project/project-layout-client'

async function getProject(projectId: string) {
  const token = cookies().get('auth_token')?.value
  const res = await fetch(
    `${process.env.API_URL}/api/v2/projects/${projectId}/`,
    {
      headers: { Authorization: `Token ${token}` },
      next: { revalidate: 60 },
    }
  )
  if (!res.ok) return null
  return res.json()
}

export default async function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: { projectId: string }
}) {
  const project = await getProject(params.projectId)

  return (
    <ProjectLayoutClient project={project}>
      {children}
    </ProjectLayoutClient>
  )
}
```

### 3.5 Create Loading States

```typescript
// app/projects/[projectId]/occurrences/loading.tsx
import { Skeleton } from '@/design-system/components/skeleton'

export default function OccurrencesLoading() {
  return (
    <div className="p-6">
      <Skeleton className="h-8 w-48 mb-4" />
      <div className="grid grid-cols-4 gap-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <Skeleton key={i} className="h-48" />
        ))}
      </div>
    </div>
  )
}
```

### 3.6 Create Error Boundaries

```typescript
// app/projects/[projectId]/occurrences/error.tsx
'use client'

import { useEffect } from 'react'
import { Button } from '@/design-system/components/button'

export default function OccurrencesError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="p-6 text-center">
      <h2 className="text-xl font-semibold mb-4">
        Something went wrong loading occurrences
      </h2>
      <Button onClick={() => reset()}>Try again</Button>
    </div>
  )
}
```

### 3.7 Migrate Modal Routes (Intercepting Routes)

For occurrence details modal that opens over the list:

```
app/projects/[projectId]/occurrences/
├── page.tsx                    # List view
├── loading.tsx                 # List loading
├── [id]/
│   └── page.tsx               # Full page detail
├── @modal/
│   └── (.)[id]/
│       └── page.tsx           # Modal detail (intercepts)
└── layout.tsx                  # Handles modal slot
```

```typescript
// app/projects/[projectId]/occurrences/layout.tsx
export default function OccurrencesLayout({
  children,
  modal,
}: {
  children: React.ReactNode
  modal: React.ReactNode
}) {
  return (
    <>
      {children}
      {modal}
    </>
  )
}

// app/projects/[projectId]/occurrences/@modal/(.)][id]/page.tsx
import { OccurrenceDetailsModal } from '@/components/occurrence-details-modal'

export default function OccurrenceModal({
  params,
}: {
  params: { id: string }
}) {
  return <OccurrenceDetailsModal id={params.id} />
}
```

---

## Phase 4: Component Updates

### 4.1 Add 'use client' Directives

Create script to identify components needing 'use client':

```bash
# Find components using client-side features
grep -r "useState\|useEffect\|useContext\|onClick\|onChange" \
  --include="*.tsx" src/ | cut -d: -f1 | sort -u
```

### 4.2 Update Navigation Imports

```typescript
// Before (React Router)
import { Link, useNavigate, useParams, useLocation } from 'react-router-dom'

// After (Next.js)
import Link from 'next/link'
import { useRouter, useParams, usePathname, useSearchParams } from 'next/navigation'

// Usage changes:
// navigate('/path') → router.push('/path')
// <Link to="/path"> → <Link href="/path">
// location.pathname → pathname (from usePathname)
// location.search → searchParams (from useSearchParams)
```

### 4.3 Update React Query Hooks for SSR

```typescript
// data-services/hooks/occurrences/useOccurrences.ts
'use client'

import { useQuery } from '@tanstack/react-query'

interface UseOccurrencesOptions {
  params?: FetchParams
  initialData?: OccurrenceListResponse
}

export function useOccurrences({ params, initialData }: UseOccurrencesOptions = {}) {
  return useQuery({
    queryKey: ['occurrences', params],
    queryFn: () => fetchOccurrences(params),
    initialData,
    // Don't refetch on mount if we have initial data from server
    refetchOnMount: !initialData,
  })
}
```

---

## Phase 5: Testing & Validation

### 5.1 Run Both Versions in Parallel

```bash
# Terminal 1: Vite dev server (existing)
yarn dev

# Terminal 2: Next.js dev server
yarn dev:next
```

Compare functionality between ports 3000 (Vite) and 3001 (Next.js).

### 5.2 Create Migration Checklist

For each route, verify:
- [ ] Page renders correctly
- [ ] Data loads (SSR or client-side)
- [ ] Navigation works (links, back button)
- [ ] Forms submit correctly
- [ ] Authentication redirects work
- [ ] Loading states display
- [ ] Errors are handled
- [ ] URL parameters work
- [ ] Filters persist
- [ ] Mobile responsive

### 5.3 Update Tests

```typescript
// Jest setup for Next.js
// jest.setup.js
import '@testing-library/jest-dom'

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
  }),
  useParams: () => ({}),
  usePathname: () => '',
  useSearchParams: () => new URLSearchParams(),
}))
```

---

## Phase 6: Cleanup & Cutover

### 6.1 Remove Vite Files

```bash
rm vite.config.ts
rm vite-env.d.ts
rm -rf src/  # After moving all components to app/ and components/
```

### 6.2 Update package.json

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  }
}
```

Remove Vite dependencies:
```bash
yarn remove vite @vitejs/plugin-react vite-tsconfig-paths \
  vite-plugin-svgr vite-plugin-eslint react-router-dom \
  react-helmet-async
```

### 6.3 Update Docker Configuration

```dockerfile
# compose/local/ui/Dockerfile
FROM node:18-alpine

WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install

COPY . .

# For development
CMD ["yarn", "dev"]

# For production
# RUN yarn build
# CMD ["yarn", "start"]
```

### 6.4 Update CI/CD

- Update build commands
- Update test commands
- Update deployment scripts
- Configure Next.js caching

---

## Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 0: Preparation | 1-2 days | None |
| Phase 1: Parallel Setup | 1-2 days | Phase 0 |
| Phase 2: Core Infrastructure | 2-3 days | Phase 1 |
| Phase 3: Route Migration | 2-3 weeks | Phase 2 |
| Phase 4: Component Updates | 1 week | Ongoing with Phase 3 |
| Phase 5: Testing | 1 week | Phase 3-4 |
| Phase 6: Cleanup | 2-3 days | Phase 5 |

**Total estimated time**: 6-8 weeks

---

## Rollback Plan

If critical issues arise:

1. Keep `main` branch unchanged until migration complete
2. Maintain Vite config in separate branch during migration
3. Docker Compose can switch between builds:
   ```yaml
   ui:
     build:
       context: ./ui
       # target: vite  # Uncomment to rollback
       target: nextjs
   ```
4. Feature flag for gradual rollout if needed

---

## Success Criteria

- [ ] All routes accessible and functional
- [ ] Authentication flow works end-to-end
- [ ] All CRUD operations work
- [ ] Gallery navigation works
- [ ] Map components render
- [ ] Charts display correctly
- [ ] Export functionality works
- [ ] Job monitoring works
- [ ] No console errors
- [ ] Performance metrics improved (LCP, FCP)
- [ ] All tests passing
- [ ] Docker build succeeds
- [ ] CI/CD pipeline green
