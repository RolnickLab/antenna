# Testing and Evaluation Plan (Remix)

## Overview

Testing strategy for the Remix migration, focusing on validating the new loader/action patterns and ensuring feature parity.

---

## 1. Pre-Migration Baseline

Same as Next.js plan - capture current metrics before migration:

- Lighthouse scores
- Bundle sizes
- Test coverage percentage
- Feature inventory
- Screenshot baseline

See `../07-testing-evaluation.md` for complete baseline checklist.

---

## 2. Remix-Specific Testing

### 2.1 Loader Testing

```typescript
// __tests__/routes/projects.$projectId.occurrences.test.ts
import { loader } from '~/routes/projects.$projectId.occurrences'
import { createRequest } from '~/test-utils'

describe('Occurrences Loader', () => {
  it('returns occurrences for valid project', async () => {
    const request = createRequest('/projects/1/occurrences', {
      token: 'valid-token',
    })

    const response = await loader({
      request,
      params: { projectId: '1' },
      context: {},
    })

    const data = await response.json()
    expect(data.results).toBeDefined()
    expect(data.count).toBeGreaterThanOrEqual(0)
  })

  it('respects filter params', async () => {
    const request = createRequest(
      '/projects/1/occurrences?taxon=123&score_min=0.8',
      { token: 'valid-token' }
    )

    const response = await loader({
      request,
      params: { projectId: '1' },
      context: {},
    })

    // Verify API was called with correct filters
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('taxon=123'),
      expect.anything()
    )
  })

  it('redirects to login without auth', async () => {
    const request = createRequest('/projects/1/occurrences', {
      token: null,
    })

    await expect(
      loader({ request, params: { projectId: '1' }, context: {} })
    ).rejects.toEqual(
      expect.objectContaining({
        status: 302,
        headers: expect.objectContaining({
          location: expect.stringContaining('/auth/login'),
        }),
      })
    )
  })
})
```

### 2.2 Action Testing

```typescript
// __tests__/routes/projects.$projectId.occurrences.$id.test.ts
import { action } from '~/routes/projects.$projectId.occurrences.$id'
import { createFormRequest } from '~/test-utils'

describe('Occurrence Actions', () => {
  it('handles agree intent', async () => {
    const request = createFormRequest({
      intent: 'agree',
      predictionId: '456',
    }, { token: 'valid-token' })

    const response = await action({
      request,
      params: { projectId: '1', id: '123' },
      context: {},
    })

    const data = await response.json()
    expect(data.success).toBe(true)
  })

  it('handles suggest intent', async () => {
    const request = createFormRequest({
      intent: 'suggest',
      taxonId: '789',
    }, { token: 'valid-token' })

    const response = await action({
      request,
      params: { projectId: '1', id: '123' },
      context: {},
    })

    const data = await response.json()
    expect(data.success).toBe(true)
  })

  it('returns error for unknown intent', async () => {
    const request = createFormRequest({
      intent: 'unknown',
    }, { token: 'valid-token' })

    const response = await action({
      request,
      params: { projectId: '1', id: '123' },
      context: {},
    })

    expect(response.status).toBe(400)
  })
})
```

### 2.3 Test Utilities

```typescript
// app/test-utils.ts
import { createCookieSessionStorage } from '@remix-run/node'

const sessionStorage = createCookieSessionStorage({
  cookie: { name: '__test_session', secrets: ['test-secret'] },
})

export async function createRequest(
  url: string,
  options: { token?: string | null } = {}
) {
  const session = await sessionStorage.getSession()
  if (options.token) {
    session.set('token', options.token)
  }

  return new Request(`http://localhost${url}`, {
    headers: {
      Cookie: await sessionStorage.commitSession(session),
    },
  })
}

export async function createFormRequest(
  data: Record<string, string>,
  options: { token?: string | null; method?: string } = {}
) {
  const formData = new FormData()
  Object.entries(data).forEach(([key, value]) => {
    formData.append(key, value)
  })

  const session = await sessionStorage.getSession()
  if (options.token) {
    session.set('token', options.token)
  }

  return new Request('http://localhost/test', {
    method: options.method || 'POST',
    body: formData,
    headers: {
      Cookie: await sessionStorage.commitSession(session),
    },
  })
}
```

---

## 3. Integration Testing

### 3.1 Route Integration Tests

```typescript
// __tests__/integration/occurrences.test.tsx
import { createRemixStub } from '@remix-run/testing'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import OccurrencesRoute, {
  loader as occurrencesLoader,
} from '~/routes/projects.$projectId.occurrences'

describe('Occurrences Integration', () => {
  it('renders occurrences from loader', async () => {
    const RemixStub = createRemixStub([
      {
        path: '/projects/:projectId/occurrences',
        Component: OccurrencesRoute,
        loader: () => ({
          results: [
            { id: '1', determination: { name: 'Species A' } },
            { id: '2', determination: { name: 'Species B' } },
          ],
          count: 2,
        }),
      },
    ])

    render(<RemixStub initialEntries={['/projects/1/occurrences']} />)

    await waitFor(() => {
      expect(screen.getByText('Species A')).toBeInTheDocument()
      expect(screen.getByText('Species B')).toBeInTheDocument()
    })
  })

  it('updates URL when filter changes', async () => {
    const user = userEvent.setup()
    const RemixStub = createRemixStub([
      {
        path: '/projects/:projectId/occurrences',
        Component: OccurrencesRoute,
        loader: () => ({ results: [], count: 0 }),
      },
    ])

    render(<RemixStub initialEntries={['/projects/1/occurrences']} />)

    // Interact with filter
    await user.click(screen.getByTestId('score-filter'))
    await user.click(screen.getByText('0.8+'))

    // URL should update
    await waitFor(() => {
      expect(window.location.search).toContain('score_min=0.8')
    })
  })
})
```

### 3.2 Form Submission Tests

```typescript
// __tests__/integration/login.test.tsx
import { createRemixStub } from '@remix-run/testing'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import LoginRoute, {
  action as loginAction,
  loader as loginLoader,
} from '~/routes/auth.login'

describe('Login Integration', () => {
  it('shows validation errors', async () => {
    const user = userEvent.setup()
    const RemixStub = createRemixStub([
      {
        path: '/auth/login',
        Component: LoginRoute,
        loader: loginLoader,
        action: async () => ({
          errors: { form: 'Invalid credentials' },
        }),
      },
    ])

    render(<RemixStub initialEntries={['/auth/login']} />)

    await user.type(screen.getByLabelText(/email/i), 'test@test.com')
    await user.type(screen.getByLabelText(/password/i), 'wrong')
    await user.click(screen.getByRole('button', { name: /log in/i }))

    await screen.findByText('Invalid credentials')
  })

  it('shows loading state during submission', async () => {
    const user = userEvent.setup()
    // ... test pending state
  })
})
```

---

## 4. E2E Testing (Playwright)

```typescript
// e2e/occurrences.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Occurrences', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto('/auth/login')
    await page.fill('[name="email"]', 'test@example.com')
    await page.fill('[name="password"]', 'password')
    await page.click('button[type="submit"]')
    await page.waitForURL('/projects')
  })

  test('displays occurrence gallery', async ({ page }) => {
    await page.goto('/projects/1/occurrences')

    // Wait for data to load
    await expect(page.locator('[data-testid="occurrence-card"]').first()).toBeVisible()
  })

  test('filters update URL and reload data', async ({ page }) => {
    await page.goto('/projects/1/occurrences')

    // Apply filter
    await page.click('[data-testid="filter-score"]')
    await page.click('text=0.8+')

    // URL should update
    await expect(page).toHaveURL(/score_min=0\.8/)

    // Loading indicator should appear then disappear
    await expect(page.locator('[data-testid="loading"]')).toBeVisible()
    await expect(page.locator('[data-testid="loading"]')).not.toBeVisible()
  })

  test('agree button submits and reloads', async ({ page }) => {
    await page.goto('/projects/1/occurrences/1')

    // Click agree
    await page.click('button:has-text("Agree")')

    // Button should show loading
    await expect(page.locator('button:has-text("Agreeing...")')).toBeVisible()

    // Then return to normal
    await expect(page.locator('button:has-text("Agree")')).toBeVisible()
  })
})
```

---

## 5. Pattern Compliance Tests

### 5.1 Loader Pattern Checklist

For each route with a loader:

```typescript
// __tests__/patterns/loader-compliance.test.ts
import { glob } from 'glob'
import * as fs from 'fs'

describe('Loader Pattern Compliance', () => {
  const routeFiles = glob.sync('app/routes/**/*.tsx')

  routeFiles.forEach((file) => {
    const content = fs.readFileSync(file, 'utf-8')
    const hasLoader = content.includes('export async function loader')
    const hasRequireAuth = content.includes('requireAuth(request)')

    if (hasLoader && !file.includes('auth.')) {
      it(`${file} should use requireAuth`, () => {
        expect(hasRequireAuth).toBe(true)
      })
    }
  })
})
```

### 5.2 Action Pattern Checklist

```typescript
describe('Action Pattern Compliance', () => {
  // Similar pattern checking for actions
  // - Uses intent pattern for multiple actions
  // - Returns json() responses
  // - Handles errors properly
})
```

---

## 6. Performance Testing

### 6.1 Loader Performance

```typescript
// __tests__/performance/loaders.test.ts
describe('Loader Performance', () => {
  it('occurrences loader completes within 500ms', async () => {
    const start = performance.now()

    await loader({
      request: createRequest('/projects/1/occurrences'),
      params: { projectId: '1' },
      context: {},
    })

    const duration = performance.now() - start
    expect(duration).toBeLessThan(500)
  })
})
```

### 6.2 Bundle Size Tracking

```bash
# Track bundle sizes
npm run build
ls -la build/client/assets/*.js | awk '{print $5, $9}'
```

Compare to pre-migration baseline.

---

## 7. Migration Verification Checklist

### 7.1 Route-by-Route

| Route | Loader Works | Action Works | UI Matches | URL State | Navigation |
|-------|-------------|--------------|------------|-----------|------------|
| `/auth/login` | N/A | ✅ | ✅ | N/A | ✅ |
| `/projects` | ✅ | N/A | ✅ | N/A | ✅ |
| `/projects/:id` | ✅ | N/A | ✅ | N/A | ✅ |
| `/projects/:id/occurrences` | ✅ | N/A | ✅ | ✅ | ✅ |
| `/projects/:id/occurrences/:id` | ✅ | ✅ | ✅ | N/A | ✅ |
| ... | | | | | |

### 7.2 Feature Parity

| Feature | Vite Version | Remix Version | Parity |
|---------|-------------|---------------|--------|
| Login/logout | ✅ | ✅ | ✅ |
| Project list | ✅ | ✅ | ✅ |
| Occurrence gallery | ✅ | ✅ | ✅ |
| Filtering | ✅ | ✅ | ✅ |
| Sorting | ✅ | ✅ | ✅ |
| Pagination | ✅ | ✅ | ✅ |
| Agree/suggest ID | ✅ | ✅ | ✅ |
| Job creation | ✅ | ✅ | ✅ |
| Job progress | ✅ | ✅ | ✅ |
| File upload | ✅ | ✅ | ✅ |
| Maps | ✅ | ✅ | ✅ |
| Charts | ✅ | ✅ | ✅ |

---

## 8. Sign-Off Criteria

### Must Pass

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] All E2E tests pass
- [ ] No TypeScript errors
- [ ] No console errors in browser
- [ ] All routes accessible
- [ ] Authentication works
- [ ] All CRUD operations work
- [ ] Performance equal or better

### Should Pass

- [ ] Lighthouse scores maintained or improved
- [ ] Bundle size reduced or equal
- [ ] Loading states visible
- [ ] Error states handled gracefully

### Nice to Have

- [ ] Progressive enhancement works (JS disabled)
- [ ] Mobile responsive maintained
- [ ] Accessibility maintained

---

## 9. POC Evaluation Criteria

For the initial 2-3 route POC:

### Quantitative

| Metric | Current | POC Target |
|--------|---------|------------|
| Lines of code (routes) | X | < X |
| Number of files | X | < X |
| Build time | X sec | < X sec |
| Bundle size | X KB | < X KB |

### Qualitative

- [ ] Pattern feels natural to the team
- [ ] Less code than React Query version
- [ ] Easier to understand for newcomers
- [ ] AI agents produce correct patterns

### Go/No-Go Decision

**Proceed if**:
- Quantitative metrics show improvement
- Team finds pattern intuitive
- No blocking issues discovered

**Reconsider if**:
- Pattern feels awkward
- Significant features harder to implement
- Performance regressions
