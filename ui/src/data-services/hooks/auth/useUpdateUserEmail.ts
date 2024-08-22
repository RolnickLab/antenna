import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useUpdateUserEmail = (onSuccess?: () => void) => {
  const queryClient = useQueryClient()
  const { user } = useUser()
  const { mutate, isLoading, isSuccess, error } = useMutation({
    mutationFn: (data: { current_password: string; new_email: string }) =>
      axios
        .post(`${API_URL}/${API_ROUTES.USERS}/set_email/`, data, {
          headers: getAuthHeader(user),
        })
        .then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.ME])
      onSuccess?.()
    },
  })

  return { updateUserEmail: mutate, isLoading, isSuccess, error }
}
