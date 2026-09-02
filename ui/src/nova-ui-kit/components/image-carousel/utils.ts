import _ from 'lodash'
import { CSSProperties } from 'react'

export const getImageBoxStyles = (
  width: string | number = 100
): CSSProperties => ({
  width: _.isNumber(width) ? `${width}px` : width,
})

export const getPlaceholderStyles = (ratio = 1): CSSProperties => ({
  paddingBottom: `${(1 / ratio) * 100}%`,
})
