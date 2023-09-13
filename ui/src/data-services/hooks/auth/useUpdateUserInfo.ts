import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useUpdateUserInfo = () => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutate, isLoading, error, isSuccess } = useMutation({
    mutationFn: (fieldValues: any) => {
      const data = new FormData()
      if (fieldValues.name) {
        data.append('name', fieldValues.name)
      }
      if (fieldValues.image) {
        data.append('image', fieldValues.image, fieldValues.image.name)
      } else if (fieldValues.image === null) {
        data.append('image', '')
      }

      return axios.patch(`${API_URL}/${API_ROUTES.ME}/`, data, {
        headers: {
          ...getAuthHeader(user),
          'Content-Type': 'multipart/form-data',
        },
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.ME])
    },
  })

  return { updateUserInfo: mutate, isLoading, error, isSuccess }
}
