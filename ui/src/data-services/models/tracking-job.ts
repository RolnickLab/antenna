import { STRING, translate } from 'utils/language'

export type TrackingScope =
  | { type: 'session'; sessionId: string }
  | { type: 'captureSet'; captureSetId: string }

export interface TrackingJobFieldValues {
  /** Left empty, the server's default threshold applies. */
  costThreshold?: string | number
  name?: string
  projectId: string
  requireFeatures: boolean
  scope: TrackingScope
}

export interface ServerTrackingConfig {
  cost_threshold?: number
  event_ids?: number[]
  require_features: boolean
  source_image_collection_id?: number
}

export interface ServerTrackingJobPayload {
  job_type_key: 'post_processing'
  name: string
  params: { task: 'tracking'; config: ServerTrackingConfig }
  project_id: number
}

const toId = (value: string, label: string) => {
  const id = Number(value)

  if (!Number.isInteger(id) || id <= 0) {
    throw new Error(`${label} must be a positive whole number, got "${value}"`)
  }

  return id
}

const toCostThreshold = (value?: string | number) => {
  if (value === undefined || value === '') {
    return undefined
  }

  const threshold = Number(value)

  if (!Number.isFinite(threshold) || threshold < 0) {
    throw new Error(`Cost threshold must be zero or more, got "${value}"`)
  }

  return threshold
}

export const getDefaultTrackingJobName = (scope: TrackingScope) =>
  scope.type === 'session'
    ? translate(STRING.TRACKING_JOB_NAME_SESSION, { id: scope.sessionId })
    : translate(STRING.TRACKING_JOB_NAME_CAPTURE_SET, {
        id: scope.captureSetId,
      })

export const buildTrackingJobPayload = ({
  costThreshold,
  name,
  projectId,
  requireFeatures,
  scope,
}: TrackingJobFieldValues): ServerTrackingJobPayload => {
  const threshold = toCostThreshold(costThreshold)
  const config: ServerTrackingConfig = {
    ...(scope.type === 'session'
      ? { event_ids: [toId(scope.sessionId, 'Session ID')] }
      : {
          source_image_collection_id: toId(
            scope.captureSetId,
            'Capture set ID'
          ),
        }),
    ...(threshold !== undefined ? { cost_threshold: threshold } : {}),
    require_features: requireFeatures,
  }

  return {
    job_type_key: 'post_processing',
    name: name?.trim() || getDefaultTrackingJobName(scope),
    params: { task: 'tracking', config },
    project_id: toId(projectId, 'Project ID'),
  }
}

export interface TrackingScopeFormValues {
  captureSetId?: string
  scopeType: TrackingScope['type']
  sessionId?: string
}

/** The scope a form describes, or undefined until its chosen field is filled in. */
export const toTrackingScope = ({
  captureSetId,
  scopeType,
  sessionId,
}: TrackingScopeFormValues): TrackingScope | undefined => {
  if (scopeType === 'session') {
    return sessionId
      ? { type: 'session', sessionId: `${sessionId}` }
      : undefined
  }

  return captureSetId ? { type: 'captureSet', captureSetId } : undefined
}
