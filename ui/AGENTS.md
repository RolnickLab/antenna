# CLAUDE.md — Frontend (ui/)

Conventions for the React + TypeScript frontend. Each rule below maps to a recurring
review finding in this repository's PR history.

**Stack:** React 18 + TypeScript + Vite + TanStack React Query. Reusable components live
in `src/design-system/` — check there before writing a new component.

## Strings & i18n

- All user-facing strings go through the translation layer: `translate(STRING.KEY)` from
  `src/utils/language.ts`. Add new keys to the `STRING` enum and `ENGLISH_STRINGS` map.
  Never hardcode UI copy in components.
- UI copy uses sentence case: "Taxa list", not "Taxa List".

## Data services & types

- No `any` for API payloads. Every endpoint gets a `Server<Entity>` interface in
  `src/data-services/models/` (the ESLint `no-explicit-any` rule is off, so this is not
  machine-enforced — reviewers will catch it).
- Server state goes through React Query hooks in `src/data-services/hooks/` — one hook
  per endpoint, follow the existing naming.
- Form value → DRF serializer behavior (empty string vs null vs undefined):
  `docs/claude/reference/react-form-to-drf-values.md`.

## Mutations & async state

- Disable mutation buttons while the request is in flight (React Query v4 exposes this
  as `isLoading` on the mutation). A fast double-click must not enqueue duplicate jobs.
- Don't seed `useState` from a value that arrives asynchronously — it won't update when
  the data lands. Derive from props/query data, or sync with an effect.
- Handle empty and null states explicitly — API fields can be null even when the
  surrounding payload is present (a missing guard here has shipped 500-driven blank
  screens before).

## Accessibility

- Interactive elements need accessible labels; progress elements need `aria-valuetext`.

## Naming & files

- File names are kebab-case: `taxa-list.ts`, not `taxalist.ts`.
- Constants are SCREAMING_SNAKE with word separation: `TAXA_LISTS`, not `TAXALISTS`.
- Don't shadow global/DOM types (`Response`, `string`) with local interface names.

## Constants

- A magic number used by one module is a `const` at the top of that module:
  `const MAX_NUM_RESULTS = 5` in `components/taxon-search/useTaxonSearch.ts`.
- Hoist to `data-services/constants.ts` only once a second module in a different
  directory needs the same value. That file holds cross-cutting values —
  `REFETCH_INTERVAL`, `SUCCESS_TIMEOUT` — not per-page settings.

## Comments

The general rule in `.agents/AGENTS.md` is written for the Python side. The frontend
runs leaner: most components carry no comments at all, so a block of prose stands out
far more here than the same block would in a Django view.

- One or two lines, and only where the code cannot say it. Anything longer belongs in
  the PR description with a `See #NNNN` pointer left behind.
- Match the file you are editing. Before adding a comment, look at its siblings — if
  they have none, the bar for adding one is high.
- State each reason once. A rationale repeated in a constant, a prop, and the code that
  uses them is one comment spread over three files.
- Comments on an exported prop or constant document the contract for its callers. Say
  what a caller must decide, not how the internals work.

Before committing, compare your comment density with the neighbours:

```bash
cd ui && for f in src/path/to/dir/*.tsx; do
  echo "$(grep -c '^\s*//' "$f")/$(wc -l < "$f")  $(basename "$f")"
done
```

Standing out by several times the local ratio means trimming, not justifying.

## Lint & format — what is actually configured

- ESLint: `ui/.eslintrc.json` — `eslint:recommended` + `@typescript-eslint/recommended`;
  `no-console` warns; `no-explicit-any` is OFF.
- Prettier: `ui/.prettierrc.json` — 2-space indent, no semicolons, single quotes.
- **There is no Stylelint config.** Review bots regularly cite Stylelint rules anyway —
  ignore findings for rules that are not in the configs above.
- Run before pushing: `cd ui && yarn lint && yarn format`.

## Commands

```bash
cd ui
nvm install      # Node version from .nvmrc
yarn install
yarn start       # Dev server on port 3000; Vite proxies /api → Django (API_PROXY_TARGET)
yarn test
yarn build
```
