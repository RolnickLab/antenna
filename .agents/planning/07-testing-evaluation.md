# Testing and Evaluation Plan

## Overview

This document outlines a comprehensive strategy for testing and validating the Next.js migration to ensure all functionality works correctly. Testing spans automated tests, manual verification, performance benchmarks, and user acceptance criteria.

---

## 1. Pre-Migration Baseline

### 1.1 Establish Current Metrics

Before migration, capture baseline metrics:

**Performance Metrics** (use Chrome DevTools Lighthouse):
```
| Metric | Current Value | Target |
|--------|---------------|--------|
| First Contentful Paint (FCP) | ___ms | < FCP |
| Largest Contentful Paint (LCP) | ___ms | < LCP |
| Time to Interactive (TTI) | ___ms | < TTI |
| Total Blocking Time (TBT) | ___ms | < TBT |
| Cumulative Layout Shift (CLS) | ___ | < CLS |
| Bundle Size (JS) | ___KB | < Size |
```

**Functional Baseline**:
- [ ] Document all existing features
- [ ] Screenshot each page/view
- [ ] Record current test coverage percentage
- [ ] List known bugs/issues

### 1.2 Create Feature Inventory

Complete checklist of all features:

```
## Authentication
- [ ] Login with email/password
- [ ] Logout
- [ ] Password reset request
- [ ] Password reset confirmation
- [ ] Session persistence
- [ ] Auto-redirect when not authenticated

## Projects
- [ ] List projects
- [ ] Create project
- [ ] Edit project settings
- [ ] Delete project
- [ ] View project summary/dashboard
- [ ] Project member management

## Deployments
- [ ] List deployments
- [ ] Create deployment
- [ ] Edit deployment
- [ ] Delete deployment
- [ ] Sync from S3 source
- [ ] View deployment details
- [ ] Map location editing

## Events/Sessions
- [ ] List events
- [ ] View event timeline
- [ ] Filter by date range

## Captures (Source Images)
- [ ] Gallery view
- [ ] Table view
- [ ] Image upload
- [ ] Star/unstar images
- [ ] Filter by deployment
- [ ] Filter by date
- [ ] Pagination

## Occurrences
- [ ] Gallery view
- [ ] Table view
- [ ] Detail modal
- [ ] Filter by taxon
- [ ] Filter by score threshold
- [ ] Filter by date range
- [ ] Filter by deployment
- [ ] Sort by various fields
- [ ] Keyboard navigation
- [ ] Pagination

## Identifications
- [ ] View ML predictions
- [ ] View human identifications
- [ ] Agree with prediction
- [ ] Suggest alternative ID
- [ ] Remove identification
- [ ] Taxa autocomplete/search

## Jobs
- [ ] List jobs
- [ ] Create new job
- [ ] View job details
- [ ] Queue job for processing
- [ ] Cancel running job
- [ ] Retry failed job
- [ ] View job progress
- [ ] View job logs

## Pipelines & ML
- [ ] List pipelines
- [ ] View pipeline details
- [ ] Configure project pipelines
- [ ] Test pipeline

## Processing Services
- [ ] List services
- [ ] View service status
- [ ] Register pipelines from service
- [ ] Health check status

## Exports
- [ ] List exports
- [ ] Create export
- [ ] Download export
- [ ] View export status

## Collections
- [ ] List collections
- [ ] Create collection
- [ ] View collection
- [ ] Add images to collection

## Settings
- [ ] General settings
- [ ] Team management
- [ ] Default filters
- [ ] Storage configuration
- [ ] Processing settings
- [ ] Sites management
- [ ] Devices management
```

---

## 2. Automated Testing Strategy

### 2.1 Unit Tests

**Configuration for Next.js:**

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
  collectCoverageFrom: [
    'app/**/*.{ts,tsx}',
    'components/**/*.{ts,tsx}',
    'data-services/**/*.{ts,tsx}',
    '!**/*.d.ts',
    '!**/node_modules/**',
  ],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 70,
      lines: 70,
      statements: 70,
    },
  },
}

module.exports = createJestConfig(customJestConfig)
```

```javascript
// jest.setup.js
import '@testing-library/jest-dom'

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    forward: jest.fn(),
    refresh: jest.fn(),
    prefetch: jest.fn(),
  }),
  useParams: () => ({}),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
  useSelectedLayoutSegment: () => null,
  useSelectedLayoutSegments: () => [],
}))

// Mock next/image
jest.mock('next/image', () => ({
  __esModule: true,
  default: (props) => <img {...props} />,
}))
```

**Test Categories:**

| Category | Files | Priority |
|----------|-------|----------|
| Domain Models | `data-services/models/*.test.ts` | High |
| Utility Functions | `utils/*.test.ts` | High |
| Custom Hooks | `data-services/hooks/*.test.ts` | High |
| UI Components | `components/**/*.test.tsx` | Medium |
| Design System | `design-system/**/*.test.tsx` | Medium |

### 2.2 Integration Tests

Test data fetching and component integration:

```typescript
// __tests__/pages/occurrences.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { OccurrencesList } from '@/components/occurrences-list'

const mockOccurrences = [
  { id: '1', determination: { name: 'Species A' }, score: 0.95 },
  { id: '2', determination: { name: 'Species B' }, score: 0.87 },
]

describe('Occurrences Page', () => {
  it('renders occurrence list with initial data', async () => {
    const queryClient = new QueryClient()

    render(
      <QueryClientProvider client={queryClient}>
        <OccurrencesList initialData={{ results: mockOccurrences, count: 2 }} />
      </QueryClientProvider>
    )

    await waitFor(() => {
      expect(screen.getByText('Species A')).toBeInTheDocument()
      expect(screen.getByText('Species B')).toBeInTheDocument()
    })
  })

  it('filters occurrences by score threshold', async () => {
    // Test filter functionality
  })
})
```

### 2.3 End-to-End Tests

Use Playwright for E2E testing:

```typescript
// e2e/auth.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('should login successfully', async ({ page }) => {
    await page.goto('/auth/login')

    await page.fill('input[name="email"]', 'antenna@insectai.org')
    await page.fill('input[name="password"]', 'localadmin')
    await page.click('button[type="submit"]')

    await expect(page).toHaveURL('/projects')
    await expect(page.locator('h1')).toContainText('Projects')
  })

  test('should redirect unauthenticated users to login', async ({ page }) => {
    await page.goto('/projects')
    await expect(page).toHaveURL('/auth/login')
  })

  test('should logout successfully', async ({ page }) => {
    // Login first
    await page.goto('/auth/login')
    await page.fill('input[name="email"]', 'antenna@insectai.org')
    await page.fill('input[name="password"]', 'localadmin')
    await page.click('button[type="submit"]')

    // Then logout
    await page.click('[data-testid="user-menu"]')
    await page.click('[data-testid="logout-button"]')

    await expect(page).toHaveURL('/auth/login')
  })
})
```

```typescript
// e2e/occurrences.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Occurrences', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/auth/login')
    await page.fill('input[name="email"]', 'antenna@insectai.org')
    await page.fill('input[name="password"]', 'localadmin')
    await page.click('button[type="submit"]')
  })

  test('should display occurrence gallery', async ({ page }) => {
    await page.goto('/projects/1/occurrences')

    await expect(page.locator('[data-testid="occurrence-grid"]')).toBeVisible()
    await expect(page.locator('[data-testid="occurrence-card"]').first()).toBeVisible()
  })

  test('should open occurrence detail modal', async ({ page }) => {
    await page.goto('/projects/1/occurrences')

    await page.locator('[data-testid="occurrence-card"]').first().click()

    await expect(page.locator('[data-testid="occurrence-modal"]')).toBeVisible()
  })

  test('should filter by taxon', async ({ page }) => {
    await page.goto('/projects/1/occurrences')

    await page.click('[data-testid="filter-taxon"]')
    await page.fill('[data-testid="taxon-search"]', 'Lepidoptera')
    await page.click('[data-testid="taxon-option-lepidoptera"]')

    await expect(page).toHaveURL(/taxon=/)
  })
})
```

### 2.4 Visual Regression Tests

Use Playwright for screenshot comparison:

```typescript
// e2e/visual.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Visual Regression', () => {
  test('occurrences page matches snapshot', async ({ page }) => {
    await page.goto('/projects/1/occurrences')
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveScreenshot('occurrences-page.png', {
      maxDiffPixelRatio: 0.01,
    })
  })

  test('occurrence detail modal matches snapshot', async ({ page }) => {
    await page.goto('/projects/1/occurrences/1')
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveScreenshot('occurrence-detail.png', {
      maxDiffPixelRatio: 0.01,
    })
  })
})
```

---

## 3. Manual Testing Checklist

### 3.1 Route-by-Route Verification

For each migrated route, verify:

```
## Route: /auth/login
- [ ] Page loads without errors
- [ ] Form renders correctly
- [ ] Email input accepts input
- [ ] Password input masks characters
- [ ] Submit button is clickable
- [ ] Validation errors display
- [ ] Successful login redirects to /projects
- [ ] "Forgot password" link works
- [ ] Responsive on mobile

## Route: /projects
- [ ] Page loads without errors
- [ ] Project list displays
- [ ] "New Project" button visible (if permitted)
- [ ] Click project navigates to project page
- [ ] Pagination works
- [ ] Sort options work
- [ ] Search/filter works
- [ ] Loading state shows during fetch
- [ ] Error state shows on failure

## Route: /projects/[projectId]/occurrences
- [ ] Page loads without errors
- [ ] Gallery view displays images
- [ ] Table view toggles correctly
- [ ] Filters panel opens/closes
- [ ] Taxon filter works
- [ ] Score filter works
- [ ] Date range filter works
- [ ] Deployment filter works
- [ ] Clear filters works
- [ ] Sorting works (each column)
- [ ] Pagination works
- [ ] Clicking occurrence opens modal
- [ ] Modal close returns to list
- [ ] URL updates with filters
- [ ] Back button preserves filters
- [ ] Keyboard navigation (arrows) works
- [ ] Loading skeleton shows
- [ ] Empty state shows when no results

## Route: /projects/[projectId]/occurrences/[id]
- [ ] Detail view loads
- [ ] Image displays correctly
- [ ] Detection bounding boxes render
- [ ] ML predictions display
- [ ] Human identifications display
- [ ] "Agree" button works
- [ ] "Suggest ID" opens autocomplete
- [ ] Taxa autocomplete searches API
- [ ] New ID submission works
- [ ] Previous/Next navigation works
- [ ] Close button works
- [ ] Escape key closes modal

(Continue for all routes...)
```

### 3.2 Cross-Browser Testing

Test on:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] Chrome Mobile (Android)
- [ ] Safari Mobile (iOS)

### 3.3 Responsive Testing

Test at breakpoints:
- [ ] 320px (mobile portrait)
- [ ] 480px (mobile landscape)
- [ ] 768px (tablet)
- [ ] 1024px (desktop)
- [ ] 1440px (large desktop)
- [ ] 1920px (full HD)

### 3.4 Accessibility Testing

- [ ] Screen reader navigation (VoiceOver/NVDA)
- [ ] Keyboard-only navigation
- [ ] Color contrast ratios
- [ ] Focus indicators visible
- [ ] Alt text on images
- [ ] ARIA labels present
- [ ] Form labels associated

---

## 4. Performance Testing

### 4.1 Lighthouse Audits

Run Lighthouse on key pages:

```bash
# Install lighthouse CLI
npm install -g lighthouse

# Run audit
lighthouse http://localhost:3000/projects/1/occurrences \
  --output html \
  --output-path ./lighthouse-report.html
```

**Pages to audit:**
- `/` (home)
- `/projects` (project list)
- `/projects/[id]/occurrences` (main gallery)
- `/projects/[id]/deployments` (deployment list)
- `/projects/[id]/jobs` (job list)

### 4.2 Core Web Vitals

Track these metrics:

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| LCP | ≤ 2.5s | 2.5s - 4s | > 4s |
| FID | ≤ 100ms | 100ms - 300ms | > 300ms |
| CLS | ≤ 0.1 | 0.1 - 0.25 | > 0.25 |

### 4.3 Bundle Analysis

```bash
# Install bundle analyzer
npm install @next/bundle-analyzer

# Add to next.config.js
const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
})

module.exports = withBundleAnalyzer(nextConfig)

# Run analysis
ANALYZE=true npm run build
```

**Review:**
- [ ] No duplicate dependencies
- [ ] Large libraries code-split
- [ ] Unused exports tree-shaken
- [ ] Compare to pre-migration bundle size

### 4.4 Server-Side Performance

Measure server response times:

```bash
# Time to first byte for SSR pages
curl -w "TTFB: %{time_starttransfer}s\n" -o /dev/null -s \
  http://localhost:3000/projects/1/occurrences
```

---

## 5. API Compatibility Testing

### 5.1 Verify All API Calls

Test each API endpoint is called correctly:

```typescript
// Mock API and verify calls
import { rest } from 'msw'
import { setupServer } from 'msw/node'

const server = setupServer(
  rest.get('/api/v2/occurrences/', (req, res, ctx) => {
    // Verify query params
    expect(req.url.searchParams.get('project')).toBe('1')
    expect(req.url.searchParams.get('limit')).toBe('20')

    return res(ctx.json({ results: [], count: 0 }))
  })
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

### 5.2 Authentication Header Verification

Ensure auth token is sent correctly:

```typescript
// Intercept and verify auth header
rest.get('/api/v2/projects/', (req, res, ctx) => {
  const authHeader = req.headers.get('Authorization')
  expect(authHeader).toMatch(/^Token .+/)
  return res(ctx.json({ results: [] }))
})
```

### 5.3 Error Handling

Test error scenarios:

- [ ] 401 Unauthorized → Redirect to login
- [ ] 403 Forbidden → Show permission error
- [ ] 404 Not Found → Show not found page
- [ ] 500 Server Error → Show error boundary
- [ ] Network timeout → Show retry option

---

## 6. Regression Testing

### 6.1 Comparison Testing

Run both versions side-by-side:

```bash
# Terminal 1: Vite version
PORT=3000 yarn dev:vite

# Terminal 2: Next.js version
PORT=3001 yarn dev:next
```

For each feature, compare:
- [ ] Visual appearance matches
- [ ] Behavior matches
- [ ] Performance equal or better
- [ ] No console errors

### 6.2 Data Integrity

Verify data displays correctly:

- [ ] All fields render
- [ ] Numbers format correctly
- [ ] Dates display in correct timezone
- [ ] Special characters render
- [ ] Long text truncates properly
- [ ] Empty states handle gracefully

---

## 7. Security Testing

### 7.1 Authentication Security

- [ ] Token not exposed in URLs
- [ ] Token stored securely (httpOnly if using cookies)
- [ ] Logout clears all stored tokens
- [ ] Protected routes redirect correctly
- [ ] Expired tokens handled gracefully

### 7.2 XSS Prevention

- [ ] User input is escaped in display
- [ ] No dangerouslySetInnerHTML without sanitization
- [ ] Content-Security-Policy headers set

### 7.3 CSRF Protection

- [ ] State-changing operations use CSRF tokens
- [ ] SameSite cookie attribute set

---

## 8. Acceptance Criteria

### 8.1 Must Have (P0)

- [ ] All existing features work identically
- [ ] No data loss or corruption
- [ ] Authentication works correctly
- [ ] Performance equal or better
- [ ] No console errors in production
- [ ] All automated tests pass

### 8.2 Should Have (P1)

- [ ] Improved Lighthouse scores
- [ ] Reduced bundle size
- [ ] Faster initial page load
- [ ] Loading states for all async operations
- [ ] Error boundaries on all pages

### 8.3 Nice to Have (P2)

- [ ] Server-side rendering on key pages
- [ ] Image optimization implemented
- [ ] Streaming for large data sets
- [ ] Edge middleware for auth

---

## 9. Test Environment Setup

### 9.1 Test Database

```bash
# Create test fixtures
docker compose run --rm django python manage.py create_demo_project

# Ensure consistent test data
docker compose run --rm django python manage.py dumpdata \
  --natural-foreign --natural-primary \
  -e contenttypes -e auth.Permission \
  > fixtures/test_data.json
```

### 9.2 CI Pipeline

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'yarn'

      - name: Install dependencies
        run: yarn install --frozen-lockfile

      - name: Run unit tests
        run: yarn test --coverage

      - name: Run E2E tests
        run: yarn test:e2e

      - name: Build
        run: yarn build

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 10. Sign-Off Checklist

### 10.1 Development Sign-Off

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] All E2E tests pass
- [ ] No TypeScript errors
- [ ] No ESLint errors
- [ ] Code review completed
- [ ] Documentation updated

### 10.2 QA Sign-Off

- [ ] Manual testing complete
- [ ] Cross-browser testing complete
- [ ] Mobile testing complete
- [ ] Accessibility testing complete
- [ ] Performance testing complete
- [ ] Security testing complete

### 10.3 Stakeholder Sign-Off

- [ ] Demo to stakeholders
- [ ] Feedback addressed
- [ ] Production deployment approved

---

## 11. Rollback Plan

If critical issues found post-deployment:

1. **Immediate**: Revert to previous Vite build
2. **Short-term**: Deploy hotfix to Next.js version
3. **Rollback command**:
   ```bash
   git revert HEAD --no-edit
   git push origin main
   # CI/CD redeploys previous version
   ```
4. **Monitoring**: Watch error rates for 24 hours post-rollback
