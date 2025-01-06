# Antenna Data Platform UI

Web interface to explore data from automated insect monitoring stations. We use React and TypeScript for the implementation. The project was setup using [Vite](https://vitejs.dev/).

## System requirements

- Node
- Yarn

The `.nvmrc` file in project root describes what Node version to use to make sure we all use the same. To switch between Node versions, a version manager, such as [Node Version Manager (NVM)](https://github.com/nvm-sh/nvm), is suggested.

## Getting started

```bash
# Install dependencies
yarn install

# Run app in development mode
yarn start
```

Now you can navigate to the following URL: http://localhost:3000

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

We use [Netlify](https://www.netlify.com/) for deployment. Changes pushed to main branch are automatically deployed to https://app.preview.insectai.org/. When a pull request is opened, a preview version of the changes will be deployed. The URL to the preview deploy will be visible as a PR comment.
