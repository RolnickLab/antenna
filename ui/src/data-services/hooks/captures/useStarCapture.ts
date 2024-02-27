import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'


export const useStarCapture = (id: string, isStarred: boolean, onSuccess?: () => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const captureDetailUrl = `${API_URL}/${API_ROUTES.CAPTURES}/${id}`
  const mutationUrl = isStarred ? `${captureDetailUrl}/unstar/` : `${captureDetailUrl}/star/`

  const { mutateAsync, isLoading, isSuccess, error } = useMutation({
    mutationFn: () =>
      axios.post(mutationUrl, {}, {
        headers: getAuthHeader(user),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.CAPTURES])
      onSuccess?.()
    },
  })

  return { starCapture: mutateAsync, isLoading, isSuccess, error }
}

