import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  convertMergeCandidate,
  MergeCandidate,
  ServerMergeCandidate,
} from 'data-services/models/merge-candidate'
import { useMemo } from 'react'
import { STRING } from 'utils/language'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const DEFAULT_WINDOW_MINUTES = 5

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

/**
 * Occurrences this one could be merged with, ranked by the tracking method.
 *
 * Fetched only while `enabled`: a merge dialog opens for one occurrence at a time,
 * and the list is keyed under the occurrences route so a completed track edit
 * refreshes it along with everything else.
 */
export const useMergeCandidates = ({
  captures,
  enabled,
  minutes = DEFAULT_WINDOW_MINUTES,
  occurrenceId,
  overlapping = false,
  projectId,
}: {
  /** Captures either side of the occurrence to search. Given, it replaces the `minutes` window. */
  captures?: number
  enabled?: boolean
  minutes?: number
  occurrenceId: string
  /** Also list occurrences seen at the same time; they are never the continuation of a track. */
  overlapping?: boolean
  projectId: string
}): {
  candidates: MergeCandidate[]
  isLoading: boolean
  error?: unknown
  captures?: number
  /** The window searched when no `captures` scope is given. */
  minutes: number
  overlapping: boolean
  /** Overlapping occurrences found, listed or not; undefined until the response arrives. */
  overlappingCount?: number
} => {
  const params = new URLSearchParams({ project_id: projectId })

  if (captures !== undefined) {
    params.set('captures', `${captures}`)
  } else {
    params.set('minutes', `${minutes}`)
  }

  if (overlapping) {
    params.set('overlapping', 'true')
  }

  const { data, isLoading, error } = useAuthorizedQuery<{
    candidates: ServerMergeCandidate[]
    overlapping_count: number
  }>({
    enabled: !!occurrenceId && !!enabled,
    queryKey: [
      API_ROUTES.OCCURRENCES,
      occurrenceId,
      'merge-candidates',
      { captures, minutes, overlapping, projectId },
    ],
    url: `${API_URL}/${API_ROUTES.OCCURRENCES}/${occurrenceId}/merge-candidates/?${params}`,
  })

  const candidates = useMemo(
    () => data?.candidates.map(convertMergeCandidate) ?? [],
    [data]
  )

  return {
    candidates,
    // A disabled query still reports itself as loading, so guard on the inputs.
    isLoading: !!occurrenceId && !!enabled && isLoading,
    error,
    captures,
    minutes,
    overlapping,
    overlappingCount: data?.overlapping_count,
  }
}
