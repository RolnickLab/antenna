# Outstanding Questions, Risks, and Alternatives (Remix)

## Outstanding Questions

### Q1: Keep React Query or Go Pure Remix?

**Question**: Should we keep React Query for any use cases?

**Pure Remix Approach**:
- All data via loaders
- All mutations via actions
- Simpler mental model
- Automatic revalidation

**Hybrid Approach** (Keep React Query for):
- Real-time polling (job progress)
- Optimistic updates (like/agree buttons)
- Complex client-side caching
- Infinite scroll

**Recommendation**: Start with pure Remix. Add React Query back only if specific features require it. Remix's `useFetcher` handles most optimistic update cases.

### Q2: Form Handling Strategy

**Question**: Use Remix `<Form>` everywhere or keep react-hook-form?

**Remix Forms**:
- Work without JavaScript
- Simpler for basic forms
- Built-in pending states

**react-hook-form**:
- Complex validation (cross-field, async)
- Dynamic forms (add/remove fields)
- Better TypeScript integration
- Array fields

**Recommendation**:
- Use Remix `<Form>` for simple forms (login, settings)
- Keep react-hook-form for complex forms (deployment config, job creation)

### Q3: Modal/Dialog Pattern

**Question**: How to handle occurrence detail modal that overlays the list?

**Options**:

1. **Outlet-based modal**:
   ```
   routes/
   ├── projects.$projectId.occurrences.tsx      # List
   └── projects.$projectId.occurrences.$id.tsx  # Full page OR modal
   ```

2. **Client-side modal** (current pattern):
   - Keep modal state client-side
   - Fetch data with `useFetcher`

3. **Parallel routes** (experimental in Remix):
   - More complex setup

**Recommendation**: Use `useFetcher` for modal data. Keeps URL for detail page, uses modal for in-context viewing.

### Q4: Authentication Session vs Token

**Question**: Switch fully to cookie sessions or keep hybrid?

**Pure Cookie Sessions**:
- Simpler for SSR
- httpOnly security
- No client-side token management

**Token in Cookie + localStorage**:
- Backwards compatible
- Can still use token for API calls in browser

**Recommendation**: Pure cookie sessions. Remix loaders/actions always have access. No need for client-side token.

### Q5: Deployment Infrastructure

**Question**: Where to deploy Remix?

| Option | Pros | Cons |
|--------|------|------|
| Node.js (Docker) | Consistent with Django | No edge |
| Vercel | Easy, edge support | Another vendor |
| Fly.io | Docker + edge | Learning curve |
| Cloudflare | Edge-first | Workers limitations |

**Recommendation**: Node.js in Docker (same as current). Simplest path, consistent infra.

---

## Risk Factors

### High Risk

#### R1: Learning Curve for Loader/Action Pattern
**Risk**: Team (including AI agents) needs to learn new data flow patterns.

**Likelihood**: Medium
**Impact**: Medium (temporary slowdown)

**Mitigation**:
- Remix patterns are well-documented
- Create internal pattern guide
- Migrate simple routes first
- Pair programming on first routes

**Detection**: Review first few PRs carefully for pattern adherence.

#### R2: Lost React Query Features
**Risk**: Some features harder to implement without React Query.

**Specific concerns**:
- Optimistic updates
- Background refetching
- Cache persistence
- Infinite scroll

**Mitigation**:
- Remix's `useFetcher` handles most optimistic updates
- Can add React Query back for specific features
- Test job progress polling early

**Detection**: Test interactive features thoroughly.

### Medium Risk

#### R3: Bundle Size Changes
**Risk**: Remix might produce different bundle sizes than Vite.

**Likelihood**: Medium
**Impact**: Low

**Mitigation**:
- Measure before/after
- Remix generally produces smaller bundles (server handles more)
- Can tune code splitting

#### R4: Leaflet/Plotly SSR Issues
**Risk**: Client-only libraries cause hydration errors.

**Likelihood**: High (known issue)
**Impact**: Low (known solution)

**Mitigation**:
- Lazy load with `lazy()` and `Suspense`
- Use `.client.tsx` suffix for client-only modules
- Test map/chart components early

#### R5: Session Secret Management
**Risk**: Session secrets need secure management.

**Likelihood**: Low
**Impact**: High if compromised

**Mitigation**:
- Use environment variable
- Rotate secrets periodically
- Use strong random secrets

### Low Risk

#### R6: URL Structure Changes
**Risk**: URLs might need adjustment for Remix conventions.

**Likelihood**: Low
**Impact**: Low

**Mitigation**:
- Remix supports same URL patterns
- Can add redirects for any changes

#### R7: Testing Infrastructure Changes
**Risk**: Test setup needs modification.

**Likelihood**: High
**Impact**: Low

**Mitigation**:
- Remix has testing utilities
- Most component tests stay same
- Integration tests need route testing

---

## Comparison: Remix vs Next.js vs Stay

| Factor | Stay (Vite) | Next.js | Remix |
|--------|-------------|---------|-------|
| **Migration effort** | None | 6-8 weeks | 6-7 weeks |
| **Boilerplate reduction** | None | Low | **High** |
| **Opinionated patterns** | None | Medium | **High** |
| **Learning curve** | None | Medium | Medium |
| **Form handling** | Manual | Basic | **Built-in** |
| **Data flow** | Manual | Flexible | **Prescribed** |
| **Community size** | Large | **Largest** | Medium |
| **Django-like feel** | No | Somewhat | **Most** |
| **Risk** | Low | Medium | Medium |
| **Intern onboarding** | Harder | Medium | **Easier** |

---

## Benefits Summary (Remix-Specific)

### For Small Teams (2 devs + interns)

1. **Prescribed Patterns = Less Debate**
   - "Where does data loading go?" → Loader
   - "Where do mutations go?" → Action
   - "How do forms work?" → `<Form>`

2. **Less Code to Maintain**
   - ~28 fewer files (hooks → loaders/actions)
   - ~40% less glue code
   - Community maintains framework

3. **External Documentation**
   - Interns can read Remix docs
   - AI assistants know Remix patterns
   - Stack Overflow answers apply

4. **Progressive Enhancement**
   - Forms work without JS
   - Graceful degradation
   - Better accessibility by default

### For AI Agents

1. **Predictable Structure**
   - Route file = page + data + mutations
   - Standard patterns AI knows
   - Less context needed

2. **Type Safety**
   - Loader → useLoaderData typed
   - Action → useActionData typed
   - Forms have known patterns

### Versus Next.js

| Aspect | Next.js | Remix |
|--------|---------|-------|
| Forms | ❌ Basic/manual | ✅ First-class |
| Mutations | ⚠️ Server Actions (newer) | ✅ Actions (mature) |
| URL State | ❌ Manual | ✅ Built-in |
| Data revalidation | ⚠️ Manual/cache tags | ✅ Automatic |
| Mental model | "Pages + APIs" | "Routes as full-stack" |
| DRF similarity | Low | **Higher** |

---

## Recommendation

### Go with Remix if:
- ✅ You want maximum boilerplate reduction
- ✅ Form handling is a significant pain point
- ✅ You value prescribed patterns over flexibility
- ✅ You want "DRF for frontend" philosophy
- ✅ Progressive enhancement matters

### Consider Next.js if:
- You need maximum ecosystem/community size
- You want Vercel's deployment experience
- SSG/ISR are important (not for Antenna)
- You prefer more flexibility

### Stay with Vite if:
- Risk tolerance is very low
- Current setup is "good enough"
- Team has no bandwidth for migration

---

## Final Assessment for Antenna

Given your stated motivations:

| Motivation | Remix Fit |
|------------|-----------|
| Reduce boilerplate | ⭐⭐⭐⭐⭐ |
| Stop reinventing patterns | ⭐⭐⭐⭐⭐ |
| Opinionated framework | ⭐⭐⭐⭐⭐ |
| Established places for things | ⭐⭐⭐⭐⭐ |
| Small team leverage | ⭐⭐⭐⭐⭐ |
| Intern/AI compatibility | ⭐⭐⭐⭐ |

**Recommendation**: **Proceed with Remix migration**

Remix aligns better with your goals than Next.js. The loader/action pattern provides the prescribed structure you're looking for, similar to how DRF provides structure for the backend.

### Suggested Approach

1. **Week 1**: POC with 2-3 routes (login, projects list, one detail page)
2. **Evaluate**: Does it feel simpler? Is the pattern clear?
3. **If yes**: Continue with full migration
4. **If no**: Reconsider alternatives

The POC approach minimizes risk while testing whether Remix delivers on the promise of reduced boilerplate.
