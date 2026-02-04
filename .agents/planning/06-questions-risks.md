# Outstanding Questions, Risks, and Alternatives

## Outstanding Questions

### Architecture Questions

#### Q1: Server Components vs Client Components Balance
**Question**: What percentage of pages should be Server Components?

**Considerations**:
- Occurrences page has heavy filtering that updates URL params → mostly client
- Project dashboard with summary stats → could be server
- Gallery with real-time updates → must be client
- Settings pages → mixed

**Research Needed**:
- Profile current page load times to establish baseline
- Identify which pages would benefit most from SSR
- Determine if SEO matters for this application (likely not - authenticated content)

#### Q2: Authentication Strategy
**Question**: Should we use cookies, localStorage, or both for auth tokens?

**Options**:
| Approach | Pros | Cons |
|----------|------|------|
| Cookies only | SSR access, more secure | CSRF concerns, httpOnly complexity |
| localStorage only | Simple, current approach | No SSR access, XSS vulnerable |
| Both (hybrid) | Best of both | More complexity |

**Recommendation**: Hybrid approach with cookie for SSR + localStorage for client consistency.

**Research Needed**:
- Review Django CSRF token handling
- Determine if httpOnly cookies work with current API setup
- Test middleware auth flow

#### Q3: API Route Handlers (BFF)
**Question**: Should we add Next.js API routes as a Backend-for-Frontend layer?

**Use Cases**:
- Aggregate multiple Django endpoints (reduce waterfalls)
- Add server-side caching for expensive queries
- Transform API responses before sending to client

**Research Needed**:
- Identify slowest/most complex API calls
- Measure if aggregation would improve performance
- Consider maintenance overhead of BFF layer

#### Q4: Image Optimization Strategy
**Question**: Should we use next/image for all images or selectively?

**Considerations**:
- Gallery images: Many small thumbnails → next/image could help
- Detection crops: Dynamic URLs from ML pipeline → needs remote patterns
- User uploads: Variable sizes → optimization valuable

**Research Needed**:
- Test next/image with MinIO URLs
- Measure gallery performance improvement
- Check if blur placeholders work with remote images

#### Q5: Deployment Target
**Question**: Where will Next.js be deployed?

**Options**:
| Target | Pros | Cons |
|--------|------|------|
| Vercel | Zero config, edge functions | Vendor lock-in, cost |
| Docker (current) | Consistent with Django | No edge, more config |
| Static export | Simplest, CDN-friendly | No SSR benefits |

**Current**: Docker Compose with Node.js server seems most consistent.

**Research Needed**:
- Verify Next.js standalone output works in Docker
- Test rewrites/proxying in containerized setup
- Measure cold start times

---

## Risk Factors

### High Risk

#### R1: React Query + SSR Hydration Mismatch
**Risk**: Server-rendered data may not match client state, causing hydration errors.

**Likelihood**: Medium
**Impact**: High (broken UI, console errors)

**Mitigation**:
- Use `initialData` pattern correctly
- Disable `refetchOnMount` when using server data
- Ensure serialization is consistent (dates, BigInt, etc.)

**Detection**: Hydration mismatch warnings in console during testing.

#### R2: Authentication Race Conditions
**Risk**: Token may not be available in cookies when middleware runs.

**Likelihood**: Medium
**Impact**: High (users redirected to login incorrectly)

**Mitigation**:
- Ensure cookie is set before navigation
- Add loading state during auth transitions
- Test login/logout flows thoroughly

**Detection**: Manual testing of auth flows, automated E2E tests.

#### R3: Third-Party Library Compatibility
**Risk**: Leaflet, Plotly, or nova-ui-kit may have SSR issues.

**Likelihood**: Medium
**Impact**: Medium (specific features broken)

**Mitigation**:
- Mark these components with 'use client'
- Use dynamic imports with `ssr: false` if needed
- Test all map/chart features early

**Example**:
```typescript
const Map = dynamic(() => import('@/components/map'), { ssr: false })
```

**Detection**: Build errors, runtime errors on page load.

### Medium Risk

#### R4: Performance Regression
**Risk**: SSR overhead may slow down some operations.

**Likelihood**: Low
**Impact**: Medium

**Mitigation**:
- Benchmark before and after
- Use streaming for large data sets
- Implement proper caching strategies

**Detection**: Performance monitoring, user feedback.

#### R5: Development Velocity Slowdown
**Risk**: Team learning curve impacts delivery.

**Likelihood**: Medium
**Impact**: Medium

**Mitigation**:
- Phased migration allows gradual learning
- Keep Vite running in parallel initially
- Document patterns and gotchas

**Detection**: Sprint velocity metrics, team feedback.

#### R6: Docker Build Complexity
**Risk**: Next.js Docker builds may be more complex than Vite.

**Likelihood**: Medium
**Impact**: Low

**Mitigation**:
- Use Next.js standalone output mode
- Follow Vercel's Docker examples
- Test builds early and often

**Detection**: CI/CD failures, increased build times.

### Low Risk

#### R7: URL/Route Compatibility
**Risk**: Some URL structures may need to change.

**Likelihood**: Low
**Impact**: Low (redirects can handle)

**Mitigation**:
- Map all routes before migration
- Add redirects for changed paths
- Update any hardcoded URLs in backend/docs

#### R8: Test Suite Updates
**Risk**: Existing tests may need significant updates.

**Likelihood**: Medium
**Impact**: Low

**Mitigation**:
- Update Jest config for Next.js
- Mock next/navigation consistently
- Prioritize integration tests over unit tests

---

## Alternatives to Next.js

### Alternative 1: Stay with Vite + Add SSR

**Approach**: Use vite-plugin-ssr or Vite's experimental SSR.

**Pros**:
- Smaller change from current setup
- Vite's fast HMR preserved
- No new framework to learn

**Cons**:
- Less mature than Next.js
- Fewer built-in features
- Smaller community/ecosystem
- More manual configuration

**When to consider**: If team strongly prefers Vite and SSR benefits are minimal.

### Alternative 2: Remix

**Approach**: Migrate to Remix instead of Next.js.

**Pros**:
- Excellent data loading patterns
- Progressive enhancement focus
- Good error handling
- React Router team's framework

**Cons**:
- Smaller ecosystem than Next.js
- Fewer deployment options
- Less enterprise adoption
- Different mental model from current app

**When to consider**: If data mutations are primary concern and you want progressive enhancement.

### Alternative 3: Astro with React Islands

**Approach**: Use Astro for static shell, React for interactive parts.

**Pros**:
- Zero JS by default (great performance)
- Perfect for content-heavy sites
- Can use React components where needed

**Cons**:
- Different architecture paradigm
- Overkill for data-heavy app like Antenna
- Less suitable for complex SPA interactions

**When to consider**: If app was primarily content/documentation focused.

### Alternative 4: Keep Vite, Optimize Current Stack

**Approach**: Don't migrate, just optimize current SPA.

**Improvements possible**:
- Add route-based code splitting
- Implement skeleton loading states
- Add service worker for offline/caching
- Optimize bundle size
- Add React Query prefetching

**Pros**:
- No migration effort
- Team already familiar
- Lower risk

**Cons**:
- Misses SSR/SEO benefits
- No server components
- Manual implementation of features Next.js provides

**When to consider**: If SSR benefits don't justify migration effort.

### Alternative 5: TanStack Start (Emerging)

**Approach**: Use TanStack's new full-stack framework.

**Pros**:
- Built by React Query team
- Familiar patterns if using TanStack
- Modern architecture

**Cons**:
- Very new (still in development)
- Not production-ready
- Limited documentation/ecosystem

**When to consider**: Watch for future, but not ready for production migration.

---

## Decision Matrix

| Factor | Next.js | Vite+SSR | Remix | Stay Current |
|--------|---------|----------|-------|--------------|
| SSR Support | ★★★★★ | ★★★☆☆ | ★★★★★ | ☆☆☆☆☆ |
| Ecosystem | ★★★★★ | ★★★☆☆ | ★★★★☆ | ★★★★☆ |
| Learning Curve | ★★★☆☆ | ★★★★☆ | ★★☆☆☆ | ★★★★★ |
| Migration Effort | ★★★☆☆ | ★★★★☆ | ★★☆☆☆ | ★★★★★ |
| Performance Potential | ★★★★★ | ★★★★☆ | ★★★★★ | ★★★☆☆ |
| Community Support | ★★★★★ | ★★★☆☆ | ★★★★☆ | ★★★★☆ |
| Enterprise Adoption | ★★★★★ | ★★☆☆☆ | ★★★☆☆ | ★★★★☆ |

---

## Summary of Benefits

### Performance Benefits
1. **Faster Initial Load**: Server-rendered HTML visible before JS loads
2. **Reduced Bundle Size**: Automatic code splitting per route
3. **Image Optimization**: Built-in lazy loading, WebP/AVIF, responsive images
4. **Streaming**: Large data sets can stream to client progressively
5. **Caching**: Multi-layer caching (data, full route, router)

### Developer Experience Benefits
1. **File-based Routing**: No manual route configuration
2. **Built-in Loading/Error States**: Convention-based, consistent UX
3. **TypeScript Integration**: Better type safety for routes and params
4. **Hot Module Replacement**: Comparable to Vite
5. **Built-in Linting**: ESLint config with Next.js rules

### SEO/Accessibility Benefits
1. **Crawlable Content**: Search engines see rendered HTML
2. **Metadata API**: Easy Open Graph and Twitter cards
3. **No Flash of Unstyled Content**: Server-rendered initial state

### Operational Benefits
1. **Deployment Flexibility**: Vercel, Docker, static export
2. **Analytics Integration**: Built-in Web Vitals reporting
3. **Monitoring**: Better Sentry integration with @sentry/nextjs
4. **Incremental Adoption**: Can migrate gradually

### Future-Proofing Benefits
1. **React Server Components**: Ready for RSC patterns
2. **React 19 Features**: Early access to new React features
3. **Active Development**: Vercel invests heavily in Next.js
4. **Large Ecosystem**: Extensive plugin/integration options

---

## Recommendation

**Proceed with Next.js migration** if:
- Team has bandwidth for 6-8 week migration
- Performance improvements are valuable
- Future features will benefit from SSR/Server Components
- Willing to invest in learning new patterns

**Defer migration** if:
- Current performance is acceptable
- Team is at capacity with feature work
- SEO is not a concern (authenticated app)
- Risk tolerance is low

**Hybrid approach**:
- Start with parallel setup (Phase 1)
- Migrate one non-critical route as POC
- Measure performance difference
- Decide whether to continue based on results
