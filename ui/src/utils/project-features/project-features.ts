import { UserPermission } from 'utils/user/types'

export type ProjectFeature = 'tags' | 'tracking'

/** Flags a project owner has not switched on read as off, including while loading. */
export const hasProjectFeature = (
  featureFlags: { [key: string]: boolean } | undefined,
  feature: ProjectFeature
) => featureFlags?.[feature] === true

/** The server grants run_tracking only while tracking is on, so the flag check is a safeguard. */
export const canStartTracking = (
  project:
    | {
        featureFlags?: { [key: string]: boolean }
        userPermissions?: UserPermission[]
      }
    | undefined
) =>
  !!project?.userPermissions?.includes(UserPermission.RunTracking) &&
  hasProjectFeature(project.featureFlags, 'tracking')

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
