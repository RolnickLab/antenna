import { useMutation } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'

export const useResetPasswordConfirm = (onSuccess?: () => void) => {
  const { mutate, isLoading, isSuccess, error } = useMutation({
    mutationFn: (data: {
      new_password: string
      token?: string
      uid?: string
    }) =>
      axios
        .post(`${API_URL}/${API_ROUTES.RESET_PASSWORD_CONFIRM}/`, data)
        .then((res) => res.data.auth_token),
    onSuccess,
  })

  return { resetPasswordConfirm: mutate, isLoading, isSuccess, error }
}
