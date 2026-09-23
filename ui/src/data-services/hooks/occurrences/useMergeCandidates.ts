import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  convertMergeCandidate,
  MergeCandidate,
  ServerMergeCandidates,
} from 'data-services/models/merge-candidate'
import { useMemo } from 'react'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const DEFAULT_WINDOW_MINUTES = 5
const MAX_RETRIES = 3
const FINAL_STATUSES = [401, 403, 404]

export type MergeScopeKey = 'next' | 'near' | 'minutes5' | 'minutes30'

/** How far from the occurrence to look: a number of captures either side of it, or a time window. */
export type MergeScope = { key: MergeScopeKey; label: STRING } & (
  | { captures: number; minutes?: undefined }
  | { minutes: number; captures?: undefined }
)

export const MERGE_SCOPES: MergeScope[] = [
  { key: 'next', label: STRING.TRACK_SCOPE_NEXT, captures: 1 },
  { key: 'near', label: STRING.TRACK_SCOPE_NEAR, captures: 3 },
  { key: 'minutes5', label: STRING.TRACK_SCOPE_MINUTES_5, minutes: 5 },
  { key: 'minutes30', label: STRING.TRACK_SCOPE_MINUTES_30, minutes: 30 },
]

/** The query string of a candidates request: a capture scope replaces the minutes window. */
export const getMergeCandidatesParams = ({
  captures,
  detectionId,
  minutes = DEFAULT_WINDOW_MINUTES,
  projectId,
}: {
  captures?: number
  detectionId?: string
  minutes?: number
  projectId: string
}) => {
  const params = new URLSearchParams({ project_id: projectId })

  if (detectionId) {
    params.set('detection', detectionId)
  }
  if (captures !== undefined) {
    params.set('captures', `${captures}`)
  } else {
    params.set('minutes', `${minutes}`)
  }

  return params
}

/** The server's reason a frame cannot be scored, sent as a string or a list of them. */
export const getDetectionError = (error: unknown): string | undefined => {
  const detection = (error as { response?: { data?: { detection?: unknown } } })
    ?.response?.data?.detection
  const message =
    detection !== undefined ? ([] as unknown[]).concat(detection)[0] : undefined

  return message ? `${message}` : undefined
}

/** Retry a failed request unless the answer cannot change by asking again. */
export const shouldRetryCandidates = (failureCount: number, error: unknown) => {
  const status = (error as { response?: { status?: number } })?.response?.status

  return (
    failureCount < MAX_RETRIES &&
    (status === undefined || !FINAL_STATUSES.includes(status))
  )
}

/** The reason the server gave for a failed request, if it gave one. */
export const getServerMessage = (error: unknown): string | undefined => {
  const axiosError = error as {
    message?: string
    response?: { data?: unknown }
  }

  if (!axiosError?.response?.data) {
    return undefined
  }

  const { fieldErrors, message } = parseServerError(error)

  return message && message !== axiosError.message
    ? message
    : fieldErrors[0]?.message
}

/** A failed request must not read as an empty scope, or the operator widens it for nothing. */
export const getCandidatesEmptyMessage = (error: unknown): string =>
  getDetectionError(error) ??
  getServerMessage(error) ??
  translate(
    error
      ? STRING.TRACK_MERGE_CANDIDATES_LOAD_FAILED
      : STRING.TRACK_NO_MERGE_CANDIDATES_SCOPE
  )

/**
 * Occurrences this one could be merged with, ranked by the tracking method. Given a
 * detection, they are candidates to move that frame to, measured from it instead.
 *
 * Fetched only while `enabled`: a merge dialog opens for one occurrence at a time,
 * and the list is keyed under the occurrences route so a completed track edit
 * refreshes it along with everything else.
 */
export const useMergeCandidates = ({
  captures,
  detectionId,
  enabled,
  minutes = DEFAULT_WINDOW_MINUTES,
  occurrenceId,
  projectId,
}: {
  /** Captures either side of the occurrence to search. Given, it replaces the `minutes` window. */
  captures?: number
  /** A frame of the occurrence to rank candidates against, for moving it elsewhere. */
  detectionId?: string
  enabled?: boolean
  minutes?: number
  occurrenceId: string
  projectId: string
}): {
  candidates: MergeCandidate[]
  /** Tracking links a pair only under this cost; undefined until the list has loaded. */
  costThreshold?: number
  /** Tracking skips a pair with no vector on both sides instead of matching it on geometry. */
  requiresFeatures?: boolean
  isLoading: boolean
  error?: unknown
  captures?: number
  /** The window searched when no `captures` scope is given. */
  minutes: number
} => {
  const params = getMergeCandidatesParams({
    captures,
    detectionId,
    minutes,
    projectId,
  })

  const { data, isLoading, error } = useAuthorizedQuery<ServerMergeCandidates>({
    enabled: !!occurrenceId && !!enabled,
    queryKey: [
      API_ROUTES.OCCURRENCES,
      occurrenceId,
      'merge-candidates',
      { captures, detectionId, minutes, projectId },
    ],
    retry: shouldRetryCandidates,
    url: `${API_URL}/${API_ROUTES.OCCURRENCES}/${occurrenceId}/merge-candidates/?${params}`,
  })

  const candidates = useMemo(
    () => data?.candidates.map(convertMergeCandidate) ?? [],
    [data]
  )

  return {
    candidates,
    costThreshold: data?.cost_threshold,
    requiresFeatures: data?.requires_features,
    // A disabled query still reports itself as loading, so guard on the inputs.
    isLoading: !!occurrenceId && !!enabled && isLoading,
    error,
    captures,
    minutes,
  }
}
