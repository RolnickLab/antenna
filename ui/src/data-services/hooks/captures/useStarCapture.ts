import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useStarCapture = (id: string, onSuccess?: () => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, error, reset } = useMutation({
    mutationFn: () =>
      axios.post(`${API_URL}/${API_ROUTES.CAPTURES}/${id}/star/`, {
        headers: getAuthHeader(user),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.CAPTURES, id])
      onSuccess?.()
    },
  })

  return { starCapture: mutateAsync, isLoading, isSuccess, error }
}
