import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import {
  buildTrackingJobPayload,
  TrackingJobFieldValues,
} from 'data-services/models/tracking-job'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useCreateTrackingJob = (onSuccess?: (id: string) => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: ({
      startNow,
      ...fieldValues
    }: TrackingJobFieldValues & { startNow?: boolean }) =>
      axios.post<{ id: number }>(
        `${API_URL}/${API_ROUTES.JOBS}/${startNow ? '?start_now' : ''}`,
        buildTrackingJobPayload(fieldValues),
        { headers: getAuthHeader(user) }
      ),
    onSuccess: ({ data }) => {
      queryClient.invalidateQueries([API_ROUTES.JOBS])
      onSuccess?.(`${data.id}`)
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { createTrackingJob: mutateAsync, isLoading, isSuccess, error }
}
