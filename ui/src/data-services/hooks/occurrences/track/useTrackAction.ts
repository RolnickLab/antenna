import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

/**
 * Shared plumbing for the track editing actions on an occurrence.
 *
 * Every one of them can change which detections the occurrence holds, and any such
 * change clears the grouping confirmation server-side, so all of them invalidate rather
 * than patching the cache. Captures are invalidated alongside occurrences because a
 * capture payload carries the occurrence behind each box, which an edit can change.
 */
export const useTrackAction = <Body, Result>(
  occurrenceId: string,
  action: string
) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, data, error, isLoading, isSuccess, reset } = useMutation(
    {
      mutationFn: (body: Body) =>
        axios.post<Result>(
          `${API_URL}/${API_ROUTES.OCCURRENCES}/${occurrenceId}/${action}/`,
          body,
          { headers: getAuthHeader(user) }
        ),
      onSuccess: () => {
        queryClient.invalidateQueries([API_ROUTES.OCCURRENCES])
        queryClient.invalidateQueries([API_ROUTES.CAPTURES])
      },
    }
  )

  return {
    mutateAsync,
    result: data?.data,
    error,
    isLoading,
    isSuccess,
    reset,
  }
}

export interface TrackEditResult {
  occurrence_id: number
  occurrence_detections_count: number
  new_occurrence_id: number
  new_occurrence_detections_count: number
}

export interface OccurrenceGroupingResult {
  occurrence_id: number
  detections_count: number
  grouping_verified: boolean
  grouping_verified_at: string | null
  grouping_verified_by: string | null
}
