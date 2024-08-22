import { useMutation } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'

export const useResetPassword = (onSuccess?: () => void) => {
  const { mutate, isLoading, isSuccess, error } = useMutation({
    mutationFn: (data: { email: string }) =>
      axios
        .post(`${API_URL}/${API_ROUTES.RESET_PASSWORD}/`, data)
        .then((res) => res.data.auth_token),
    onSuccess,
  })

  return { resetPassword: mutate, isLoading, isSuccess, error }
}
