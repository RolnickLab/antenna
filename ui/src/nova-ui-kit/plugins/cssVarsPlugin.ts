import { Plugin } from 'vite'
import { CONSTANTS } from '../constants'

const flattenColors = (
  obj: Record<string, any>,
  prefix = ''
): Record<string, string> =>
  Object.entries(obj).reduce((acc, [key, value]) => {
    const varName = (prefix ? `${prefix}-${key}` : key).replace(/-DEFAULT$/, '')
    if (typeof value === 'string') {
      acc[`--color-${varName}`] = value
    } else {
      Object.assign(acc, flattenColors(value, varName))
    }
    return acc
  }, {} as Record<string, string>)

export const cssVarsPlugin = (): Plugin => ({
  name: 'css-vars',
  transformIndexHtml() {
    const colorVars = flattenColors(CONSTANTS.COLORS)
    const themeVars = flattenColors(CONSTANTS.COLOR_THEME)

    const toLines = (vars: Record<string, string>) =>
      Object.entries(vars)
        .map(([k, v]) => `  ${k}: ${v};`)
        .join('\n')

    const css = `:root {\n${toLines(colorVars)}\n\n${toLines(themeVars)}\n}`

    return [
      {
        tag: 'style',
        attrs: { 'data-css-vars': true },
        children: css,
        injectTo: 'head-prepend',
      },
    ]
  },
})
