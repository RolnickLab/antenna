import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  convertMergeCandidate,
  MergeCandidate,
  ServerMergeCandidate,
} from 'data-services/models/merge-candidate'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const DEFAULT_WINDOW_MINUTES = 5

/**
 * Occurrences this one could be merged with, ranked by the tracking method.
 *
 * Fetched only while `enabled`: a merge dialog opens for one occurrence at a time,
 * and the list is keyed under the occurrences route so a completed track edit
 * refreshes it along with everything else.
 */
export const useMergeCandidates = ({
  enabled,
  minutes = DEFAULT_WINDOW_MINUTES,
  occurrenceId,
  projectId,
}: {
  enabled?: boolean
  minutes?: number
  occurrenceId: string
  projectId: string
}): {
  candidates: MergeCandidate[]
  isLoading: boolean
  error?: unknown
  minutes: number
} => {
  const { data, isLoading, error } = useAuthorizedQuery<{
    candidates: ServerMergeCandidate[]
  }>({
    enabled: !!occurrenceId && !!enabled,
    queryKey: [
      API_ROUTES.OCCURRENCES,
      occurrenceId,
      'merge-candidates',
      { minutes, projectId },
    ],
    url: `${API_URL}/${API_ROUTES.OCCURRENCES}/${occurrenceId}/merge-candidates/?project_id=${projectId}&minutes=${minutes}`,
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
    minutes,
  }
}
