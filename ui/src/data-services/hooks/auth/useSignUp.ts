import { useMutation } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'

export const useSignUp = ({ onSuccess }: { onSuccess?: () => void } = {}) => {
  const { mutate, isLoading, isSuccess, error } = useMutation({
    mutationFn: (data: { email: string; password: string }) =>
      axios
        .post(`${API_URL}/${API_ROUTES.USERS}/`, data)
        .then((res) => res.data),
    onSuccess,
  })

  return { signUp: mutate, isLoading, isSuccess, error }
}
