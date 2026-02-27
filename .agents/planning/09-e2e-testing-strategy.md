# E2E Testing Strategy with Playwright

## Overview

This document outlines strategies for efficiently creating comprehensive E2E tests before or alongside the Remix migration. The goal is to establish a safety net that verifies the application works correctly, with minimal manual test-writing effort.

---

## Tool Selection

### Recommendation: Playwright

| Feature | Playwright | Cypress | Selenium |
|---------|------------|---------|----------|
| Multi-browser | ✅ Chrome, Firefox, Safari | ⚠️ Chrome-focused | ✅ All |
| Speed | ✅ Fast (parallel) | ⚠️ Slower | ❌ Slowest |
| Auto-wait | ✅ Built-in | ✅ Built-in | ❌ Manual |
| Codegen (recording) | ✅ Excellent | ⚠️ Basic | ❌ None |
| API testing | ✅ Built-in | ✅ Plugin | ❌ Separate |
| Visual comparison | ✅ Built-in | ⚠️ Plugin | ❌ Separate |
| Trace viewer | ✅ Excellent | ⚠️ Basic | ❌ None |
| AI-friendly | ✅ Clean API | ✅ Good | ❌ Verbose |
| Modern/maintained | ✅ Microsoft | ✅ Active | ⚠️ Legacy feel |

**Why Playwright:**
- Best codegen (recording) tool
- Excellent trace viewer for debugging
- Fast parallel execution
- Built-in visual regression
- Clean, modern API that AI can generate easily

---

## Test Generation Strategies

### Strategy 1: Playwright Codegen (Recording)

**How it works:**
```bash
npx playwright codegen http://localhost:3000
```

Opens a browser where you perform actions. Playwright records and generates test code.

**Example output:**
```typescript
test('filter occurrences by score', async ({ page }) => {
  await page.goto('http://localhost:3000/projects/1/occurrences');
  await page.getByTestId('filter-score').click();
  await page.getByText('0.8+').click();
  await expect(page).toHaveURL(/score_min=0.8/);
  await expect(page.getByTestId('occurrence-card')).toHaveCount(5);
});
```

**Efficiency tips:**
- Record happy paths first
- One recording session per user flow
- Clean up generated code (remove unnecessary waits)
- Add assertions manually after recording

**Time estimate:** 5-10 min per user flow

---

### Strategy 2: Analytics-Driven Prioritization

Use real user data to identify what to test first.

#### From Google Analytics

**Most visited pages:**
```
GA > Behavior > Site Content > All Pages
```

Prioritize E2E tests for top 10 pages by pageviews.

**Common user flows:**
```
GA > Behavior > Behavior Flow
```

Identify the most common paths users take.

**Example priority list from analytics:**
| Rank | Page/Flow | Est. % Traffic |
|------|-----------|----------------|
| 1 | Login → Projects | 100% |
| 2 | Projects → Occurrences | 80% |
| 3 | Occurrence filtering | 70% |
| 4 | Occurrence detail view | 60% |
| 5 | Agree with ID | 40% |
| 6 | Create job | 30% |
| 7 | View job progress | 25% |
| 8 | Deployments list | 20% |

**Action:** Export top flows, create test for each.

#### From NewRelic

**Transaction traces:**
```
NewRelic > APM > Transactions > Most time consuming
```

Identifies which API calls are most used → which features to test.

**Error rates by page:**
```
NewRelic > Browser > Page views > Sort by JS errors
```

Prioritize testing pages with high error rates.

**User sessions:**
```
NewRelic > Browser > Session traces
```

Watch real user sessions to understand actual usage patterns.

---

### Strategy 3: AI-Assisted Test Generation

#### Option A: Claude Code Generates from Routes

Provide Claude with:
1. Route file
2. Component code
3. API contract

Ask it to generate Playwright tests.

**Prompt example:**
```
Given this Remix route file for occurrences:
[paste loader, action, component]

Generate Playwright E2E tests covering:
1. Page loads with data
2. Filtering updates URL and reloads data
3. Pagination works
4. Error states display correctly
```

**Efficiency:** Claude can generate 10-20 tests/hour with good coverage.

#### Option B: Generate from OpenAPI Schema

The project has an OpenAPI schema (`ami-openapi-schema.yaml`).

```bash
# Generate API contract tests
npx playwright codegen --load-storage=auth.json \
  http://localhost:8000/api/v2/docs/
```

Or use tools like:
- **Optic** - API contract testing from OpenAPI
- **Dredd** - API testing from API Blueprint/OpenAPI
- **Schemathesis** - Property-based API testing

#### Option C: Generate from TypeScript Types

Use the existing TypeScript interfaces to generate test data:

```typescript
// data-services/types.ts has interfaces
// Generate test fixtures automatically

import { faker } from '@faker-js/faker'
import type { Occurrence } from './types'

export function createMockOccurrence(): Occurrence {
  return {
    id: faker.string.uuid(),
    determination: {
      id: faker.string.uuid(),
      name: faker.animal.insect(),
    },
    score: faker.number.float({ min: 0, max: 1 }),
    // ...
  }
}
```

---

### Strategy 4: Session Recording Analysis

#### Tools for Recording Real Sessions

| Tool | What it Captures | Export Format |
|------|------------------|---------------|
| **FullStory** | User sessions | Video + events |
| **Hotjar** | Heatmaps + recordings | Video |
| **LogRocket** | Sessions + errors | Video + logs |
| **NewRelic Browser** | Session traces | Event timeline |
| **Sentry Session Replay** | Error sessions | Video |

#### Converting Recordings to Tests

1. **Watch top 10 user sessions** from analytics
2. **Note the actions** users perform
3. **Record same actions** with Playwright codegen
4. **Add assertions** for expected outcomes

**Example workflow:**
```
FullStory session shows:
1. User logs in
2. Clicks project "Field Study 2024"
3. Filters occurrences by "Lepidoptera"
4. Clicks first occurrence
5. Agrees with ML prediction
6. Navigates to next occurrence

→ Record this flow in Playwright codegen
→ Add assertions for data loading
→ Save as critical-path.spec.ts
```

---

### Strategy 5: Log-Based Test Generation

#### From Application Logs

If logging user actions:
```python
# Django logs might show:
INFO user=5 action=filter_occurrences params={"taxon": "123", "score_min": "0.8"}
INFO user=5 action=agree_identification occurrence=456 prediction=789
```

Parse logs to identify:
- Most common actions
- Common parameter combinations
- Error-prone flows

#### From API Access Logs

```bash
# Parse nginx/Django access logs
cat access.log | grep "POST /api/v2/identifications" | wc -l
cat access.log | grep "GET /api/v2/occurrences" | awk '{print $7}' | sort | uniq -c | sort -rn | head -20
```

Identifies:
- Most-used endpoints
- Common query parameter combinations
- Which filters are actually used

---

## Recommended Test Structure

### Directory Layout
```
e2e/
├── fixtures/
│   ├── auth.json           # Saved auth state
│   ├── test-data.ts        # Mock data generators
│   └── api-mocks.ts        # MSW handlers for offline testing
├── pages/                  # Page Object Models
│   ├── login.page.ts
│   ├── projects.page.ts
│   ├── occurrences.page.ts
│   └── occurrence-detail.page.ts
├── tests/
│   ├── auth.spec.ts
│   ├── critical-path.spec.ts      # Most important flows
│   ├── occurrences.spec.ts
│   ├── jobs.spec.ts
│   └── visual-regression.spec.ts
├── playwright.config.ts
└── global-setup.ts         # Login once, save state
```

### Page Object Model Example

```typescript
// e2e/pages/occurrences.page.ts
import { Page, Locator, expect } from '@playwright/test'

export class OccurrencesPage {
  readonly page: Page
  readonly filterScore: Locator
  readonly filterTaxon: Locator
  readonly occurrenceCards: Locator
  readonly pagination: Locator

  constructor(page: Page) {
    this.page = page
    this.filterScore = page.getByTestId('filter-score')
    this.filterTaxon = page.getByTestId('filter-taxon')
    this.occurrenceCards = page.getByTestId('occurrence-card')
    this.pagination = page.getByTestId('pagination')
  }

  async goto(projectId: string) {
    await this.page.goto(`/projects/${projectId}/occurrences`)
  }

  async filterByScore(minScore: string) {
    await this.filterScore.click()
    await this.page.getByText(minScore).click()
    await this.page.waitForURL(/score_min=/)
  }

  async filterByTaxon(taxonName: string) {
    await this.filterTaxon.click()
    await this.page.getByPlaceholder('Search taxa').fill(taxonName)
    await this.page.getByText(taxonName).first().click()
  }

  async expectOccurrenceCount(count: number) {
    await expect(this.occurrenceCards).toHaveCount(count)
  }

  async clickOccurrence(index: number) {
    await this.occurrenceCards.nth(index).click()
  }
}
```

### Test Example Using Page Objects

```typescript
// e2e/tests/occurrences.spec.ts
import { test, expect } from '@playwright/test'
import { OccurrencesPage } from '../pages/occurrences.page'

test.describe('Occurrences', () => {
  let occurrencesPage: OccurrencesPage

  test.beforeEach(async ({ page }) => {
    occurrencesPage = new OccurrencesPage(page)
    await occurrencesPage.goto('1')
  })

  test('displays occurrence gallery', async () => {
    await expect(occurrencesPage.occurrenceCards.first()).toBeVisible()
  })

  test('filters by score update URL', async ({ page }) => {
    await occurrencesPage.filterByScore('0.8+')
    await expect(page).toHaveURL(/score_min=0\.8/)
  })

  test('filters by taxon', async ({ page }) => {
    await occurrencesPage.filterByTaxon('Lepidoptera')
    await expect(page).toHaveURL(/taxon=/)
  })

  test('clicking occurrence opens detail', async ({ page }) => {
    await occurrencesPage.clickOccurrence(0)
    await expect(page.getByTestId('occurrence-detail')).toBeVisible()
  })
})
```

---

## Visual Regression Testing

### Built-in Playwright Screenshots

```typescript
test('occurrences page visual', async ({ page }) => {
  await page.goto('/projects/1/occurrences')
  await page.waitForLoadState('networkidle')

  await expect(page).toHaveScreenshot('occurrences-gallery.png', {
    maxDiffPixelRatio: 0.01,
  })
})
```

### Before/After Migration Comparison

```bash
# Before migration: capture baselines
npx playwright test --update-snapshots

# After migration: compare
npx playwright test

# Review differences
npx playwright show-report
```

---

## Test Data Strategies

### Option A: Use Real Backend (Recommended for Migration)

```typescript
// playwright.config.ts
export default defineConfig({
  use: {
    baseURL: 'http://localhost:3000',
  },
  webServer: {
    command: 'npm run dev',
    port: 3000,
    reuseExistingServer: true,
  },
})
```

Requires `docker compose up` for Django backend.

### Option B: Mock API with MSW

```typescript
// e2e/fixtures/api-mocks.ts
import { rest } from 'msw'

export const handlers = [
  rest.get('/api/v2/occurrences/', (req, res, ctx) => {
    return res(ctx.json({
      results: [
        { id: '1', determination: { name: 'Species A' }, score: 0.95 },
        { id: '2', determination: { name: 'Species B' }, score: 0.87 },
      ],
      count: 2,
    }))
  }),
]
```

Faster but less realistic.

### Option C: Seed Database with Fixtures

```bash
# Before tests
docker compose run --rm django python manage.py loaddata e2e_fixtures.json

# After tests
docker compose run --rm django python manage.py flush --no-input
```

---

## Efficient Test Generation Plan

### Phase 1: Critical Path Tests (2 hours)

Record and verify the most important user flows:

| Test | Method | Time |
|------|--------|------|
| Login/logout | Codegen | 15 min |
| View projects | Codegen | 10 min |
| Filter occurrences | Codegen | 20 min |
| View occurrence detail | Codegen | 15 min |
| Agree with ID | Codegen | 15 min |
| Create job | Codegen | 20 min |
| View job progress | Codegen | 15 min |

**Output:** 7 critical tests covering ~80% of usage

### Phase 2: Visual Baselines (1 hour)

Capture screenshots of all major pages:

```typescript
const pages = [
  '/projects',
  '/projects/1/summary',
  '/projects/1/occurrences',
  '/projects/1/occurrences/1',
  '/projects/1/jobs',
  '/projects/1/deployments',
  '/projects/1/settings',
]

for (const path of pages) {
  test(`visual: ${path}`, async ({ page }) => {
    await page.goto(path)
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveScreenshot()
  })
}
```

**Output:** Visual regression suite for all pages

### Phase 3: Edge Cases (2 hours)

AI-generate tests for:
- Empty states (no occurrences)
- Error states (API failure)
- Pagination edge cases
- Filter combinations
- Form validation

**Method:** Provide Claude with component code, ask for edge case tests

### Phase 4: Analytics-Driven Expansion (Ongoing)

Weekly:
1. Check GA for new popular flows
2. Check error logs for broken flows
3. Add tests for uncovered areas

---

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/e2e.yml
name: E2E Tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: |
          cd ui
          npm ci
          npx playwright install --with-deps

      - name: Start services
        run: docker compose up -d

      - name: Wait for services
        run: |
          timeout 60 bash -c 'until curl -s http://localhost:8000/api/v2/ > /dev/null; do sleep 2; done'

      - name: Run E2E tests
        run: cd ui && npx playwright test

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: ui/playwright-report/
```

---

## Quick Start Commands

```bash
# Install Playwright
cd ui
npm init playwright@latest

# Record a test
npx playwright codegen http://localhost:3000

# Run tests
npx playwright test

# Run with UI mode (debugging)
npx playwright test --ui

# View report
npx playwright show-report

# Update visual snapshots
npx playwright test --update-snapshots
```

---

## Summary: Most Efficient Approach

| Method | Effort | Coverage | Quality |
|--------|--------|----------|---------|
| Codegen (recording) | Low | High for happy paths | Good |
| AI generation | Low | Medium-high | Good |
| Manual writing | High | Precise | Best |
| Analytics-driven | Medium | Targets real usage | Excellent |

**Recommended mix:**
1. **Codegen** for critical paths (7-10 tests)
2. **Visual regression** for all pages (automated)
3. **AI generation** for edge cases (10-20 tests)
4. **Analytics review** to prioritize (ongoing)

**Total initial effort:** ~5 hours for comprehensive coverage
**Ongoing effort:** ~1 hour/week to maintain and expand
