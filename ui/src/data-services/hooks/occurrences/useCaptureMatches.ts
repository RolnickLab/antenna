import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  CaptureMatch,
  convertCaptureMatches,
  ServerCaptureMatches,
} from 'data-services/models/capture-match'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

/**
 * How likely each box on a capture is the animal of the track being extended, keyed by
 * detection id. Keyed under the occurrences route so a completed track edit refreshes it.
 */
export const useCaptureMatches = ({
  captureId,
  enabled,
  occurrenceId,
}: {
  captureId?: string
  enabled?: boolean
  occurrenceId?: string
}): { matches?: Record<string, CaptureMatch> } => {
  const { data } = useAuthorizedQuery<ServerCaptureMatches>({
    enabled: !!occurrenceId && !!captureId && !!enabled,
    queryKey: [
      API_ROUTES.OCCURRENCES,
      occurrenceId,
      'capture-matches',
      captureId,
    ],
    // The boxes fall back to neutral without scores, so a failure is not worth retrying.
    retry: 0,
    staleTime: Infinity,
    url: `${API_URL}/${API_ROUTES.OCCURRENCES}/${occurrenceId}/capture-matches/?capture_id=${captureId}`,
  })

  const matches = useMemo(
    () => (data ? convertCaptureMatches(data) : undefined),
    [data]
  )

  return { matches }
}
