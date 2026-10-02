export const CROP_COLUMN_PX = 96
export const CROP_MAX_HEIGHT_PX = 120

/**
 * Pixel size of the empty box that stands in for a missing crop: the bounding box's
 * proportions fitted into the crop column, or a square filling it when they are unknown.
 */
export const missingCropSize = (
  width: number,
  height: number
): { width: number; height: number } => {
  const w = width > 0 ? width : CROP_COLUMN_PX
  const h = height > 0 ? height : CROP_COLUMN_PX
  const scale = Math.min(CROP_COLUMN_PX / w, CROP_MAX_HEIGHT_PX / h)

  return { width: Math.round(w * scale), height: Math.round(h * scale) }
}
