import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useUpdateUserInfo = () => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutate, isLoading, error, isSuccess } = useMutation({
    mutationFn: (fieldValues: any) =>
      axios.patch(`${API_URL}/${API_ROUTES.ME}/`, fieldValues, {
        headers: getAuthHeader(user),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.ME])
    },
  })

  return { updateUserInfo: mutate, isLoading, error, isSuccess }
}
