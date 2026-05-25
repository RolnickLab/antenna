import plugin from 'tailwindcss/plugin'
import { CONSTANTS } from './src/design-system/constants'

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    colors: CONSTANTS.COLORS,
    screens: {
      sm: `${CONSTANTS.BREAKPOINTS.SM}px`,
      md: `${CONSTANTS.BREAKPOINTS.MD}px`,
      lg: `${CONSTANTS.BREAKPOINTS.LG}px`,
      xl: `${CONSTANTS.BREAKPOINTS.XL}px`,
    },
    extend: {
      backgroundImage: CONSTANTS.GRADIENTS,
      colors: CONSTANTS.COLOR_THEME,
      boxShadow: {
        toolbar: '0px 4px 16px rgba(0, 0, 0, 0.1)',
      },
    },
  },
  plugins: [
    plugin(function ({ addVariant }) {
      addVariant('hover-device', '@media (hover: hover)')
    }),
  ],
}
