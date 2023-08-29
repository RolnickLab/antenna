import { StatusTheme } from './types'

export const RADIUS = 24

export const STROKE_WIDTH = 4

export const THEMES = {
  [StatusTheme.Success]: {
    bg: '#dededf', // color-neutral-200
    fg: '#09af8a', // color-success-500
  },
  [StatusTheme.Alert]: {
    bg: '#dededf', // color-neutral-200
    fg: '#f36399', // color-alert-500
  },
}
