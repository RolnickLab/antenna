import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useCreateTypedJob = (onSuccess?: (id: string) => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: ({
      body,
      startNow,
    }: {
      body: { [key: string]: unknown }
      startNow?: boolean
    }) =>
      axios.post<{ id: number }>(
        `${API_URL}/${API_ROUTES.JOBS}/${startNow ? '?start_now' : ''}`,
        body,
        { headers: getAuthHeader(user) }
      ),
    onSuccess: ({ data }) => {
      queryClient.invalidateQueries([API_ROUTES.JOBS])
      queryClient.invalidateQueries([API_ROUTES.CAPTURES])
      onSuccess?.(`${data.id}`)
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { createJob: mutateAsync, isLoading, isSuccess, error }
}
