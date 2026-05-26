# Antenna Data Platform UI

Web interface to manage and explore data from automated insect monitoring stations.

## Tech stack

- **Frontend**: [React](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/)
- **Build**: [Vite](https://vitejs.dev/)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/) + [SCSS](https://sass-lang.com/)
- **UI primitives**: [Radix](https://www.radix-ui.com/primitives) + [shadcn/ui](https://ui.shadcn.com/)
- **State management and data fetching**: [TanStack Query](https://tanstack.com/query/latest)
- **Package manager**: [Yarn](https://yarnpkg.com/)
- **Code quality**: [ESLint](https://eslint.org/) + [Prettier](https://prettier.io/)
- **Tests**: [Jest](https://jestjs.io/)
- **Deployment**: [Netlify](https://www.netlify.com/)

## Code structure

```
src/
├── components/        # Reusable UI components
├── data-services/     # API integration layer
│   ├── hooks/         # Hooks for API calls
│   ├── models/        # TypeScript data layer
├── design-system/     # Design system (colors, text styles, breakpoints, UI primitives)
├── pages/             # Page components
└── utils/             # Helper functions and utilities
```

## Development

### System requirements

- Node
- Yarn

The `.nvmrc` file in project root describes what Node version to use to make sure we all use the same. To switch between Node versions, a version manager, such as [Node Version Manager (NVM)](https://github.com/nvm-sh/nvm), is suggested.

### Getting started

```bash
# Install dependencies
yarn install

# Run app in development mode
yarn start
```

Now you can navigate to the following URL: http://localhost:3000

## Design system

The design system is centralized in the `src/design-system` directory and defines the visual language used across the application. It includes colors, typography, responsive breakpoints, and reusable UI primitives.

### Colors

Colors are defined in `src/design-system/constants.ts` and organized into both raw colors and theme colors. For consistency, use the theme colors when possible and the raw colors for special cases. Avoid hard coded colors.

Colors can be applied in different ways from code. Tailwind CSS is the recommended approach. We define colors in one place in code and generate variables for the different use cases build time.

**Tailwind CSS (recommended):**

```tsx
// Use theme colors for consistency
<div className="bg-muted text-muted-foreground border-border">
  Some text
</div>

// Use raw colors for special cases
<div className="bg-neutral-50 text-neutral-600 border-neutral-200">
  Some text
</div>
```

**SCSS:**

```scss
// Use theme colors for consistency
.box {
  background: var(--color-muted);
  color: var(--color-muted-foreground);
  border: 1px solid var(--color-border);
}

// Use raw colors for special cases
.box {
  background: var(--color-neutral-50);
  color: var(--color-neutral-600);
  border-color: var(--color-neutral-200);
}
```

**TypeScript:**

```typescript
import { CONSTANTS } from 'design-system'

const Box = () => (
  <div
    style={{
      background: CONSTANTS.COLORS.neutral[50],
      color: CONSTANTS.COLORS.neutral[500],
      borderColor: CONSTANTS.neutral[200],
    }}
  >
    Some text
  </div>
)
```

### Text styles

Text styles are defined using SCSS mixins in `design-system/mixins.scss` with the `Mazzard` font family as the primary typeface. All text styles are based on a consistent scale for font sizes and line heights. For consistency, avoid hard coded font sizes and line heights.

**Tailwind CSS (recommended):**

```tsx
<h1 className="heading-large">Some title</h1>
<p className="body-base">Some text</p>
```

**SCSS:**

```scss
.some-title {
  @include heading-large();
}

.some-text {
  @include body-base();
}
```

### Breakpoints

Responsive breakpoints are defined in `src/design-system/constants.ts`. Use these to adapt layouts to different screen sizes.

Breakpoints can be applied in different ways from code. Tailwind CSS is using a small screen first approach and makes it possible to define responsive styles in a compact and intuitive way.

**Tailwind CSS (recommended):**

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
  {/* 1 column by default, 2 columns on medium screens, 3 columns on large screens, 5 columns on extra large screens */}
</div>
```

**SCSS:**

```scss
// 5 columns by default
.box {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
}

// 3 columns on large screens
@media (max-width: $breakpoint-xl) {
  .box {
    grid-template-columns: repeat(3, 1fr);
  }
}

// 2 columns on medium screens
@media only screen and (max-width: $breakpoint-lg) {
  .box {
    grid-template-columns: repeat(2, 1fr);
  }
}

// 1 column on small screens
@media only screen and (max-width: $breakpoint-md) {
  .box {
    grid-template-columns: 1fr;
  }
}
```

### UI primitives

UI primitives are built on [Radix UI](https://www.radix-ui.com/primitives) (unstyled, accessible components) and [shadcn/ui](https://ui.shadcn.com/) (pre-styled variants). Use these instead of building custom components for better accessibility and consistency.

Components are exported from `src/design-system/index.ts` and can be imported as follows:

```tsx
import { Button } from 'design-system'

const Box = () => (
  <div>
    <Button>
      <span>Some label</span>
    </Button>
  </div>
)
```

## Code style

We use [Prettier](https://prettier.io/) as a code formatter. The project preferences are specified in `prettierrc.json`. If you are using Visual Stuido Code, the extension [Prettier - Code formatter](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode) is recommended for auto formating in editor. There is also an option to run the following commands from terminal:

```bash
# Check format for all code in folder src
yarn format --check

# Auto format all code in folder src
yarn format --write
```

We use [ESLint](https://eslint.org/) to find issues in the code. The project preferences are specified in `eslintrc.json`. If you are using Visual Stuido Code, the extension [ESLint](https://marketplace.visualstudio.com/items?itemName=dbaeumer.vscode-eslint) is recommended for highlighting lint issues in editor. There is also an option to run the following command from terminal:

```bash
# Run linter for all code in folder src
yarn lint
```

## Tests

We use [Jest](https://jestjs.io/) as a test runner. Jest will search the project for for the following files:

- Files with .test.js suffix.
- Files with .spec.js suffix.
- Files with .ts suffix in \_\_tests\_\_ folders.

To run tests:

```bash
# Launch test runner in interactive watch mode
yarn test
```

## Deployment

We use [Netlify](https://www.netlify.com/) for deployment. Changes pushed to main branch are automatically deployed. When a pull request is opened, a preview version of the changes will be deployed. The URL to the preview deploy will be visible as a PR comment.
