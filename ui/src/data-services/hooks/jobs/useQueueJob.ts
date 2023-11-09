import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useQueueJob = () => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, error } = useMutation({
    mutationFn: (id: string) =>
      axios.post<{ id: number }>(`${API_URL}/${API_ROUTES.JOBS}/${id}/run/`, {
        headers: getAuthHeader(user),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.JOBS])
      queryClient.invalidateQueries([API_ROUTES.CAPTURES])
    },
  })

  return { queueJob: mutateAsync, isLoading, isSuccess, error }
}
