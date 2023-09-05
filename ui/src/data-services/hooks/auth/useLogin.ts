import { useMutation } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { useUser } from 'utils/user/userContext'

export const useLogin = ({ onSuccess }: { onSuccess?: () => void } = {}) => {
  const { setToken } = useUser()
  const { mutate, isLoading, error } = useMutation({
    mutationFn: (data: { email: string; password: string }) =>
      axios
        .post<{ auth_token: string }>(`${API_URL}/${API_ROUTES.LOGIN}/`, data)
        .then((res) => res.data.auth_token),
    onSuccess: (token) => {
      setToken(token)
      onSuccess?.()
    },
  })

  return { login: mutate, isLoading, error }
}
