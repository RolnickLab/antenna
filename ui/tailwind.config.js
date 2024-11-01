import { CONSTANTS } from 'nova-ui-kit'

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{ts,tsx}', './node_modules/nova-ui-kit/**/*.js'],
  theme: {
    colors: CONSTANTS.COLORS,
    extend: {
      backgroundImage: CONSTANTS.GRADIENTS,
      colors: CONSTANTS.COLOR_THEME,
    },
  },
  plugins: [],
}
