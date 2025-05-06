import { CONSTANTS } from 'nova-ui-kit'
import { BREAKPOINTS } from './src/components/constants'

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{ts,tsx}', './node_modules/nova-ui-kit/**/*.js'],
  theme: {
    colors: CONSTANTS.COLORS,
    screens: {
      sm: `${BREAKPOINTS.SM}px`,
      md: `${BREAKPOINTS.MD}px`,
      lg: `${BREAKPOINTS.LG}px`,
      xl: `${BREAKPOINTS.XL}px`,
    },
    extend: {
      backgroundImage: CONSTANTS.GRADIENTS,
      colors: CONSTANTS.COLOR_THEME,
    },
  },
  plugins: [],
}
