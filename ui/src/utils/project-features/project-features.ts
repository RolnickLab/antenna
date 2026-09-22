export type ProjectFeature = 'tags' | 'tracking'

/** Flags a project owner has not switched on read as off, including while loading. */
export const hasProjectFeature = (
  featureFlags: { [key: string]: boolean } | undefined,
  feature: ProjectFeature
) => featureFlags?.[feature] === true

// Occurrence list columns that only mean something once occurrences are tracks.
export const TRACKING_COLUMN_IDS = [
  'detections',
  'motion',
  'size-change',
  'id-agreement',
]

export const withoutTrackingColumns = <T extends { id: string }>(
  columns: T[],
  trackingEnabled: boolean
) =>
  trackingEnabled
    ? columns
    : columns.filter((column) => !TRACKING_COLUMN_IDS.includes(column.id))
