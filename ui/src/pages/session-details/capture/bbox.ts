export interface BoxStyle {
  width: string
  height: string
  top: string
  left: string
}

/**
 * Place a detection box over its capture, as percentages. The dimensions must be
 * the stored ones for the box's own capture: a box from a neighbouring frame
 * scaled by the current capture's dimensions lands in the wrong place.
 */
export const bboxToPercentStyle = (
  bbox: number[],
  width?: number | null,
  height?: number | null
): BoxStyle | undefined => {
  const [boxLeft, boxTop, boxRight, boxBottom] = bbox

  if (!width || !height) {
    return undefined
  }

  return {
    width: `${((boxRight - boxLeft) / width) * 100}%`,
    height: `${((boxBottom - boxTop) / height) * 100}%`,
    top: `${(boxTop / height) * 100}%`,
    left: `${(boxLeft / width) * 100}%`,
  }
}

/** Centre of a detection box in the same percentage space, for drawing a path. */
export const bboxToPercentCentre = (
  bbox: number[],
  width?: number | null,
  height?: number | null
): { x: number; y: number } | undefined => {
  const [boxLeft, boxTop, boxRight, boxBottom] = bbox

  if (!width || !height) {
    return undefined
  }

  return {
    x: ((boxLeft + boxRight) / 2 / width) * 100,
    y: ((boxTop + boxBottom) / 2 / height) * 100,
  }
}
