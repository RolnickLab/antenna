import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { useUser } from 'utils/user/userContext'

export const useLogout = ({ onSuccess }: { onSuccess?: () => void } = {}) => {
  const queryClient = useQueryClient()
  const { clearToken, user } = useUser()
  const { mutate, isLoading, error } = useMutation({
    mutationFn: () =>
      axios.post(`${API_URL}/${API_ROUTES.LOGOUT}`, {
        headers: { Authorization: `Token ${user.token}` },
      }),
    onSuccess: () => {
      clearToken()
      queryClient.invalidateQueries([API_ROUTES.ME])
      onSuccess?.()
    },
  })

  return { logout: mutate, isLoading, error }
}
