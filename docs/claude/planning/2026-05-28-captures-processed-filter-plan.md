# Captures "Processed / Not processed" Filter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Processing status" filter (Processed / Not processed / All) to the Captures list view, reusing the existing `has_detections` backend query param.

**Architecture:** Backend already filters captures by `?has_detections=true|false` via `Exists(Detection)` (null Detection markers make "has any detection" == "was processed"). No backend logic change; add a regression test only. Frontend adds a 3-state select component (modeled on the verified filter) and wires it through the existing filter registry/URL-param machinery.

**Tech Stack:** Django 4.2 + DRF (backend), React 18 + TypeScript + nova-ui-kit Select (frontend).

Design spec: `docs/claude/planning/2026-05-28-captures-processed-filter-design.md`

---

## Task 1: Backend regression test for `has_detections` filter

No existing test covers `?has_detections=` on the captures list. Add one to lock in the behavior we depend on. This is the only backend change.

**Files:**
- Test: `ami/main/tests.py` (add a new `APITestCase` class near the other captures/list tests, e.g. after `TestProjectRequiredOnListEndpoints` ~line 1392)

- [ ] **Step 1: Write the failing test**

Add this class to `ami/main/tests.py`. The fixtures `setup_test_project`, `create_captures`, and `create_detections` are already imported / available (`create_detections` lives in `ami.tests.fixtures.main` — add it to the existing import on line 41 if not present).

Update the import line 41 to include `create_detections`:

```python
from ami.tests.fixtures.main import (
    create_captures,
    create_detections,
    create_occurrences,
    create_taxa,
    setup_test_project,
)
```

Then add the test class:

```python
class TestCapturesProcessedFilter(APITestCase):
    """
    The captures list supports ?has_detections=true|false, which the UI surfaces
    as the "Processing status" filter. A capture is "processed" when it has any
    Detection row (including null markers for "processed, found nothing").
    """

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project(reuse=False)
        self.captures = create_captures(self.deployment, num_nights=1, images_per_night=4)
        # Mark the first two captures as processed by giving them a detection.
        for capture in self.captures[:2]:
            create_detections(capture, bboxes=[(0.1, 0.1, 0.2, 0.2)])
        self.user = User.objects.create_user(email="proc-filter@insectai.org", is_staff=True)  # type: ignore
        self.client.force_authenticate(user=self.user)
        self.list_url = f"/api/v2/captures/?project_id={self.project.pk}"
        return super().setUp()

    def test_no_filter_returns_all_captures(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 4)

    def test_has_detections_true_returns_only_processed(self):
        response = self.client.get(f"{self.list_url}&has_detections=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 2)

    def test_has_detections_false_returns_only_unprocessed(self):
        response = self.client.get(f"{self.list_url}&has_detections=false")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 2)
```

- [ ] **Step 2: Run the test to verify it passes (it should — behavior already exists)**

Run:
```bash
docker compose run --rm django python manage.py test ami.main.tests.TestCapturesProcessedFilter --keepdb -v 2
```
Expected: 3 tests PASS. (This is a characterization test for existing behavior; if `test_has_detections_false` fails returning 4 instead of 2, that means null-marker handling differs — stop and investigate before touching the UI.)

- [ ] **Step 3: Commit**

```bash
git add ami/main/tests.py
git commit -m "test: cover has_detections filter on captures list endpoint

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Add label strings for the processing-status filter

**Files:**
- Modify: `ui/src/utils/language.ts` (the `STRING` enum and the string map)

- [ ] **Step 1: Add enum keys**

In the `STRING` enum in `ui/src/utils/language.ts`, add two keys (place them alphabetically near `PROCESSING`/`NOT_VERIFIED` neighbors — exact position is cosmetic):

```typescript
  NOT_PROCESSED,
  PROCESSED,
```

- [ ] **Step 2: Add the string values**

In the string-map object (where entries like `[STRING.NOT_VERIFIED]: 'Not verified',` live), add:

```typescript
  [STRING.NOT_PROCESSED]: 'Not processed',
  [STRING.PROCESSED]: 'Processed',
```

- [ ] **Step 3: Commit**

```bash
git add ui/src/utils/language.ts
git commit -m "feat(ui): add Processed / Not processed label strings

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Create the `ProcessingStatusFilter` component

A 3-state select: empty (= All, cleared via the FilterControl X button), true (Processed), false (Not processed). Modeled on `verification-status-filter.tsx`. Do NOT reuse `BooleanFilter` — its "No" branch calls `onClear()` and cannot filter to false (`boolean-filter.tsx:21-27`).

**Files:**
- Create: `ui/src/components/filtering/filters/processing-status-filter.tsx`

- [ ] **Step 1: Write the component**

```tsx
import { Select } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { booleanToString, stringToBoolean } from '../utils'
import { FilterProps } from './types'

export const ProcessingStatusFilter = ({ value: string, onAdd }: FilterProps) => {
  const value = stringToBoolean(string)
  const options = [
    { value: true, label: translate(STRING.PROCESSED) },
    { value: false, label: translate(STRING.NOT_PROCESSED) },
  ]

  return (
    <Select.Root value={booleanToString(value)} onValueChange={onAdd}>
      <Select.Trigger>
        <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
      </Select.Trigger>
      <Select.Content>
        {options.map((option) => (
          <Select.Item
            key={booleanToString(option.value)}
            value={booleanToString(option.value)}
          >
            {option.label}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/components/filtering/filters/processing-status-filter.tsx
git commit -m "feat(ui): add ProcessingStatusFilter select component

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Register the component and the filter field

**Files:**
- Modify: `ui/src/components/filtering/filter-control.tsx` (import + `ComponentMap`)
- Modify: `ui/src/utils/useFilters.ts` (`AVAILABLE_FILTERS`)

- [ ] **Step 1: Import the component in filter-control.tsx**

Add near the other filter imports (after the `PipelineFilter` import, ~line 10):

```typescript
import { ProcessingStatusFilter } from './filters/processing-status-filter'
```

- [ ] **Step 2: Register in `ComponentMap`**

In `ui/src/components/filtering/filter-control.tsx`, add to the `ComponentMap` object (keep keys alphabetical-ish; place after `pipeline:`):

```typescript
  has_detections: ProcessingStatusFilter,
```

- [ ] **Step 3: Register the filter field in `AVAILABLE_FILTERS`**

In `ui/src/utils/useFilters.ts`, add an entry to the array returned by `AVAILABLE_FILTERS` (e.g. after the `event` entry, ~line 138):

```typescript
  {
    label: 'Processing status',
    field: 'has_detections',
    tooltip: {
      text: 'Filter captures by whether they have been processed by a detection pipeline.',
    },
  },
```

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/filtering/filter-control.tsx ui/src/utils/useFilters.ts
git commit -m "feat(ui): register processing-status filter (has_detections)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Render the filter on the captures page

**Files:**
- Modify: `ui/src/pages/captures/captures.tsx` (the `FilterSection`, ~lines 65-68)

- [ ] **Step 1: Add the FilterControl**

In `ui/src/pages/captures/captures.tsx`, inside the existing `<FilterSection defaultOpen>`, add the new control below `collections`:

```tsx
        <FilterSection defaultOpen>
          <FilterControl field="deployment" />
          <FilterControl field="collections" />
          <FilterControl field="has_detections" />
        </FilterSection>
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/pages/captures/captures.tsx
git commit -m "feat(ui): show processing-status filter on captures list

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Type-check, lint, and manual verification

**Files:** none (verification only)

- [ ] **Step 1: TypeScript type check**

Run:
```bash
cd ui && yarn tsc --noEmit
```
Expected: no errors. (If `yarn tsc` is not a script, use `npx tsc --noEmit`.)

- [ ] **Step 2: Lint + format the touched files**

Run:
```bash
cd ui && yarn lint && yarn format
```
Expected: clean (or auto-fixed). Re-commit if format changed anything.

- [ ] **Step 3: Manual verification against the running stack**

Start the stack (`docker compose up -d` from repo root; for worktree code-only changes use the bind-mount Option A in CLAUDE.md if testing against the main stack). Then in the UI at `http://localhost:4000`, open a project's Captures list and:
  - Select **Processed** → URL gains `?has_detections=true`, result count drops to processed captures only.
  - Select **Not processed** → `has_detections=false`, count shows unprocessed only.
  - Click the **X** clear button → param removed, all captures return.
  - Confirm the page resets to page 1 when the filter changes (handled by `useFilters.addFilter`).

- [ ] **Step 4: Final commit (only if lint/format changed files)**

```bash
git add -A
git commit -m "chore(ui): lint/format for processing-status filter

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review notes

- **Spec coverage:** backend reuse (Task 1 verifies), new component (Task 3), registry wiring (Task 4), page render (Task 5), label strings (Task 2), testing (Tasks 1 + 6). All spec sections covered.
- **Type consistency:** component named `ProcessingStatusFilter` in Tasks 3 and 4; query field `has_detections` in Tasks 1, 4, 5; STRING keys `PROCESSED` / `NOT_PROCESSED` in Tasks 2 and 3.
- **Out of scope (later PRs):** date range, site, device filters — see design doc.
