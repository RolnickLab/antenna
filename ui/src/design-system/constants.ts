const COLORS = {
  generic: { white: '#FFFFFF', black: '#000000' },
  neutral: {
    50: '#F9F9FA',
    100: '#F4F5F6',
    200: '#DEDFE3',
    300: '#CBCDD2',
    400: '#9FA2AB',
    500: '#71747D',
    600: '#52545D',
    700: '#3E4049',
    800: '#282A31',
    900: '#171820',
  },
  primary: {
    50: '#FAFBFF',
    100: '#EEF0F9',
    200: '#DDE1F3',
    300: '#ADB4DC',
    400: '#858FC7',
    500: '#46508B',
    600: '#3B4681',
    700: '#313B72',
    800: '#2A346A',
    900: '#1C244F',
  },
  secondary: {
    50: '#F5F9FF',
    100: '#E6F0FF',
    200: '#C9DFFD',
    300: '#A7CAFB',
    400: '#82B3F7',
    500: '#5193F0',
    600: '#3181F2',
    700: '#0B6CF4',
    800: '#065AD0',
    900: '#014098',
  },
  success: {
    50: '#E5FFF9',
    100: '#B8FFF0',
    200: '#76FBDE',
    300: '#00E6B4',
    400: '#00D3A5',
    500: '#00AE87',
    600: '#009E7C',
    700: '#008A6C',
    800: '#00755C',
    900: '#004D3C',
  },
  alert: {
    50: '#FFF5F9',
    100: '#FFF0F5',
    200: '#FED7E5',
    300: '#FCBFD6',
    400: '#F99FC0',
    500: '#F476A4',
    600: '#F55691',
    700: '#F51467',
    800: '#D10550',
    900: '#980138',
  },
  warning: {
    50: '#FFF9F0',
    100: '#FFF4E0',
    200: '#FFE3B3',
    300: '#FDD187',
    400: '#F9BC53',
    500: '#F2A31F',
    600: '#E29208',
    700: '#C37D04',
    800: '#A76A01',
    900: '#754A00',
  },
  destructive: {
    50: '#FFF5F5',
    100: '#FFEBEB',
    200: '#FECDCD',
    300: '#FBB1B1',
    400: '#F78787',
    500: '#EF4444',
    600: '#EB0F0F',
    700: '#D20A0A',
    800: '#AD0505',
    900: '#830101',
  },
}

const GRADIENTS = {
  fieldguide: 'linear-gradient(103deg, #5193F0 0%, #F476A4 108%)',
  antenna:
    'linear-gradient(102deg, #858FC7 -13.31%, #606BA4 21.25%, #313B72 100%)',
}

const COLOR_THEME = {
  background: COLORS.generic.white,
  foreground: COLORS.neutral[900],
  card: {
    DEFAULT: COLORS.generic.white,
    foreground: COLORS.neutral[900],
  },
  popover: {
    DEFAULT: COLORS.generic.white,
    foreground: COLORS.neutral[900],
  },
  primary: {
    DEFAULT: COLORS.primary[600],
    foreground: COLORS.generic.white,
  },
  secondary: {
    DEFAULT: COLORS.secondary[500],
    foreground: COLORS.generic.white,
  },
  muted: {
    DEFAULT: COLORS.neutral[50],
    foreground: COLORS.neutral[600],
  },
  accent: {
    DEFAULT: COLORS.alert[500],
    foreground: COLORS.generic.white,
  },
  success: {
    DEFAULT: COLORS.success[500],
    foreground: COLORS.generic.white,
  },
  destructive: {
    DEFAULT: COLORS.destructive[500],
    foreground: COLORS.generic.white,
  },
  border: COLORS.neutral[200],
  input: COLORS.neutral[200],
  ring: COLORS.neutral[900],
}

export const CONSTANTS = {
  COLORS,
  GRADIENTS,
  COLOR_THEME,
}
