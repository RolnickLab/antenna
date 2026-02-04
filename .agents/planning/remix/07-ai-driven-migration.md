# AI-Driven Migration Plan

## Overview

This document outlines how Claude Code can execute the Remix migration in **0.5-2 hours** with automated verification at each step, minimizing the need for human oversight.

---

## Current Test Infrastructure

### What Exists

| Type | Status | Files |
|------|--------|-------|
| Unit Tests | ✅ Pass | 9 files, 29 tests |
| Lint | ✅ Pass | ESLint configured |
| TypeScript Build | ⚠️ Fails | Pre-existing issue (react-hook-form types) |
| E2E Tests | ❌ None | No Playwright/Cypress |
| Integration Tests | ❌ None | No component integration tests |

### Test Files
```
src/data-services/hooks/auth/tests/useLogout.test.ts
src/data-services/hooks/auth/tests/useAuthorizedQuery.test.ts
src/data-services/hooks/auth/tests/useLogin.test.ts
src/data-services/hooks/auth/tests/useUserInfo.test.ts
src/utils/user/userContext.test.tsx
src/utils/isEmpty/isEmpty.test.ts
src/utils/date/getCompactDatespanString/getCompactDatespanString.test.ts
src/utils/parseServerError/parseServerError.test.ts
src/utils/numberFormats/numberFormats.test.ts
```

### Verification Commands
```bash
npm run test    # 29 tests, should pass
npm run lint    # Should pass (no output = success)
npm run build   # Currently fails (pre-existing TS issue)
```

---

## Risk Assessment for AI Migration

### High Confidence (Can Verify Automatically)
- Lint errors → `npm run lint`
- Test failures → `npm run test`
- Import errors → Vite dev server errors
- Syntax errors → Build/dev server errors

### Medium Confidence (Needs Spot-Checking)
- Route structure works
- Navigation between pages
- Data loads correctly
- Forms submit

### Low Confidence (Needs Human Verification)
- Visual appearance matches
- Complex interactions (gallery, maps)
- Edge cases in filters
- Mobile responsiveness

---

## AI Migration Strategy

### Approach: Incremental with Checkpoints

Instead of big-bang migration, use small atomic changes with verification after each:

```
For each phase:
  1. Make changes
  2. Run verification commands
  3. Start dev server, check for errors
  4. Commit if passing
  5. Continue or rollback
```

### Phase Breakdown (Estimated 60-90 minutes)

#### Phase 1: Setup (10 min)
**Changes:**
- Add Remix dependencies
- Create `remix.config.js` / `vite.config.ts` for Remix
- Create `app/root.tsx`
- Create `app/entry.client.tsx`, `app/entry.server.tsx`
- Create `app/sessions.server.ts`

**Verification:**
```bash
npm install
npm run dev  # Should start without errors (even if no routes)
```

**Checkpoint:** Remix dev server starts

---

#### Phase 2: Auth Routes (10 min)
**Changes:**
- Create `app/routes/auth.login.tsx` with loader + action
- Create `app/routes/auth.logout.tsx`
- Move session logic to server utilities

**Verification:**
```bash
npm run dev
# Visit http://localhost:3001/auth/login
# - Page renders
# - Form displays
```

**Checkpoint:** Login page renders

---

#### Phase 3: Projects List (10 min)
**Changes:**
- Create `app/routes/projects._index.tsx` with loader
- Create `app/services/projects.server.ts`

**Verification:**
```bash
npm run dev
# After login, visit /projects
# - Page renders
# - Data loads (or shows loading error if no backend)
```

**Checkpoint:** Projects page renders

---

#### Phase 4: Project Layout (10 min)
**Changes:**
- Create `app/routes/projects.$projectId.tsx` (layout)
- Sidebar renders

**Verification:**
```bash
# Visit /projects/1
# - Layout renders
# - Sidebar shows
```

**Checkpoint:** Project layout works

---

#### Phase 5: Occurrences (Core Feature) (20 min)
**Changes:**
- Create `app/routes/projects.$projectId.occurrences.tsx`
- Create `app/services/occurrences.server.ts`
- Migrate filter components (keep as client components)
- URL params work for filters

**Verification:**
```bash
# Visit /projects/1/occurrences
# - Gallery renders
# - Changing filters updates URL
# - Data reloads on filter change
```

**Checkpoint:** Occurrences page works with filters

---

#### Phase 6: Occurrence Detail + Actions (15 min)
**Changes:**
- Create `app/routes/projects.$projectId.occurrences.$id.tsx`
- Add action for agree/suggest ID
- Test form submission

**Verification:**
```bash
# Visit /projects/1/occurrences/1
# - Detail page renders
# - Agree button shows pending state
# - Form submission works
```

**Checkpoint:** Mutations work

---

#### Phase 7: Remaining Routes (20 min)
**Changes:**
- Jobs, deployments, settings, etc.
- Follow same pattern

**Verification:**
```bash
# Navigate through app
# All major sections accessible
```

**Checkpoint:** All routes migrated

---

#### Phase 8: Cleanup (10 min)
**Changes:**
- Remove old React Router config
- Remove unused hooks
- Update package.json scripts

**Verification:**
```bash
npm run lint
npm run test
npm run build  # May still fail due to pre-existing issue
```

**Checkpoint:** Clean codebase

---

## Automated Verification Script

Create a script the AI can run after each phase:

```bash
#!/bin/bash
# verify.sh

echo "=== Running Lint ==="
npm run lint
LINT_STATUS=$?

echo "=== Running Tests ==="
npm run test
TEST_STATUS=$?

echo "=== Starting Dev Server (5 second check) ==="
timeout 10 npm run dev &
DEV_PID=$!
sleep 5
if ps -p $DEV_PID > /dev/null; then
    echo "Dev server started successfully"
    kill $DEV_PID
    DEV_STATUS=0
else
    echo "Dev server failed to start"
    DEV_STATUS=1
fi

echo "=== Results ==="
echo "Lint: $([ $LINT_STATUS -eq 0 ] && echo 'PASS' || echo 'FAIL')"
echo "Tests: $([ $TEST_STATUS -eq 0 ] && echo 'PASS' || echo 'FAIL')"
echo "Dev Server: $([ $DEV_STATUS -eq 0 ] && echo 'PASS' || echo 'FAIL')"

exit $(( LINT_STATUS + TEST_STATUS + DEV_STATUS ))
```

---

## What Needs More Research

### 1. Backend API Availability
**Question:** Will the Django backend be running during migration?

**If yes:**
- Can test actual data loading
- Can verify form submissions work
- Higher confidence in verification

**If no:**
- Must rely on structural verification only
- Mock API responses for testing
- Lower confidence

**Action:** Determine if `docker compose up` will be running

### 2. Visual Regression Baseline
**Question:** Should we capture screenshots before migration?

**If yes:**
- Can compare before/after
- Higher confidence in visual parity
- Adds 15-20 min to setup

**If no:**
- Rely on structural verification
- Human spot-check after completion

**Action:** Decide if visual regression is worth the setup time

### 3. TypeScript Strict Mode
**Question:** The build currently fails. Should we:
- Fix the TS issue first?
- Ignore build errors and rely on dev server?
- Downgrade TypeScript?

**Recommendation:** Ignore for migration, address separately

### 4. Parallel Running
**Question:** Can we keep old Vite version running alongside Remix?

**If yes:**
- Side-by-side comparison
- Easy rollback
- Better verification

**Setup:**
```bash
# Terminal 1: Old version
PORT=3000 npm run dev:old

# Terminal 2: New Remix version
PORT=3001 npm run dev
```

**Action:** Set up parallel dev scripts before migration

---

## Risk Mitigation

### Commit Strategy
```
After each phase that passes verification:
git add -A
git commit -m "phase N: description"
```

This allows rollback to any working state.

### Rollback Plan
```bash
# If phase N breaks things:
git reset --hard HEAD~1  # Go back one commit
# Or:
git checkout HEAD~N -- .  # Go back N commits
```

### Human Checkpoints
Even with 0.5-2 hour timeline, suggest human verification at:
1. After Phase 2 (auth works)
2. After Phase 5 (core feature works)
3. After Phase 8 (completion)

This is 3 quick checks, ~5 min each.

---

## Recommended Approach

### Option A: Full Autopilot (Higher Risk)
1. AI executes all phases
2. Runs verification after each
3. Commits passing phases
4. Human reviews at end

**Risk:** Subtle bugs may not be caught

### Option B: Semi-Supervised (Recommended)
1. AI executes phases 1-5
2. Human spot-check (5 min)
3. AI executes phases 6-8
4. Human final review (10 min)

**Risk:** Lower, 15 min human time

### Option C: Route-by-Route Approval
1. AI migrates one route
2. Human approves
3. Repeat

**Risk:** Lowest, but takes longer

---

## Pre-Migration Checklist

Before AI starts migration:

- [ ] `npm install` completed
- [ ] `npm run test` passes (29 tests)
- [ ] `npm run lint` passes
- [ ] Backend available (docker compose up) OR mock strategy decided
- [ ] Parallel dev server strategy set up
- [ ] Git branch created for migration
- [ ] This document reviewed and approved

---

## Success Criteria

Migration is complete when:

1. **Structural:**
   - [ ] All routes accessible
   - [ ] Lint passes
   - [ ] Tests pass (existing 29)
   - [ ] Dev server starts without errors

2. **Functional (requires backend):**
   - [ ] Login works
   - [ ] Projects list loads
   - [ ] Occurrences load with filters
   - [ ] Form submissions work

3. **Code Quality:**
   - [ ] No React Query hooks remain (except intentional keeps)
   - [ ] Loaders/actions follow patterns
   - [ ] Old router config removed

---

## Estimated Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Setup | 10 min | 10 min |
| Auth | 10 min | 20 min |
| Projects | 10 min | 30 min |
| Layout | 10 min | 40 min |
| Occurrences | 20 min | 60 min |
| Detail + Actions | 15 min | 75 min |
| Remaining Routes | 20 min | 95 min |
| Cleanup | 10 min | 105 min |

**Total: ~1.5-2 hours** (with verification at each step)

Could be faster (~1 hour) if:
- Skipping some verification
- Routes are simpler than expected
- No unexpected issues
