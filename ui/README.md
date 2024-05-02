# AMI Data Companion UI

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

We use [Prettier](https://prettier.io/) as a code formatter. You can setup your code editor to auto format the code you write, based on the project config. There is also an option to run the following command from terminal:

```bash
# Auto formats all code in folder src
yarn format
```

We use [ESLint](https://eslint.org/) to find issues in the code. You can setup your code editor to highlight such issues, based on the project config. There is also an option to run the following command from terminal:

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

## Storybook

We use Storybook to document our design system in code. You can read more about Storybook [here](https://storybook.js.org/).

To run Storybook locally:

```bash
# Install dependencies
yarn install

# Launch Storybook in development mode
yarn storybook
```

Now you can navigate to the following URL: http://localhost:6006

### Publish Storybook

Build Storybook as a static web application:

```bash
yarn build-storybook
```

Read more about publishing Storybook [here](https://storybook.js.org/docs/react/sharing/publish-storybook).
