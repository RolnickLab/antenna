import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useCancelJob = () => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, error } = useMutation({
    mutationFn: (id: string) =>
      axios.post<{ id: number }>(
        `${API_URL}/${API_ROUTES.JOBS}/${id}/cancel/`,
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.JOBS])
    },
  })

  return { cancelJob: mutateAsync, isLoading, isSuccess, error }
}
