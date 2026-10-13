import { API_ROUTES, API_URL } from 'data-services/constants'
import { CaptureSet, ServerCaptureSet } from 'data-services/models/capture-set'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerCaptureSet) => new CaptureSet(record)

/**
 * Load a single capture set, including the number of captures it contains.
 *
 * Pickers read their options from the choices endpoint, which reports no counts,
 * so a picker that shows the size of the selected set loads it here. Occurrence
 * and taxa counts stay off, since nothing displays them.
 */
export const useCaptureSetDetails = (
  captureSetId?: string,
  projectId?: string
): {
  captureSet?: CaptureSet
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const enabled = !!captureSetId && !!projectId
  const url = `${API_URL}/${API_ROUTES.CAPTURE_SETS}/${captureSetId}/?project_id=${projectId}&with_counts=false`

  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<ServerCaptureSet>({
      enabled,
      queryKey: [API_ROUTES.CAPTURE_SETS, captureSetId, projectId],
      url,
    })

  const captureSet = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    captureSet,
    isLoading,
    isFetching,
    error,
  }
}
