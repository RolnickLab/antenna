import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, STATUS_CODES } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useLogout = () => {
  const queryClient = useQueryClient()
  const { clearToken, user } = useUser()
  const { mutate, isLoading, error } = useMutation({
    mutationFn: () =>
      axios.post(`${API_URL}/${API_ROUTES.LOGOUT}/`, undefined, {
        headers: getAuthHeader(user),
      }),
    onSuccess: () => {
      clearToken()
      queryClient.invalidateQueries([API_ROUTES.ME])
    },
    onError: (error: any) => {
      if (error.response?.status === STATUS_CODES.FORBIDDEN) {
        clearToken()
      }
    },
  })

  return { logout: mutate, isLoading, error }
}
