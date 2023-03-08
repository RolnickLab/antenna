# AMI Platform

## Good to know

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## System requirements

- Node
- Yarn

## Getting started

```bash
# Install dependencies
yarn install

# Run the app in the development mode
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

## Storybook

We use Storybook to document our design system in code. You can read more about Storybook here.

To run Storybook locally:

```bash
# Launch Storybook in development mode
yarn storybook
```

Now you can navigate to the following URL: http://localhost:6006
