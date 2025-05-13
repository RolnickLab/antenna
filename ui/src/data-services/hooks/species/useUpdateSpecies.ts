import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useUpdateSpecies = (id: string, onSuccess?: () => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: (fieldValues: { name?: string }) => {
      const data = new FormData()

      if (fieldValues.name) {
        data.append('name', fieldValues.name)
      }

      return axios.patch(`${API_URL}/${API_ROUTES.SPECIES}/${id}/`, data, {
        headers: {
          ...getAuthHeader(user),
          'Content-Type': 'multipart/form-data',
        },
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.SPECIES])
      onSuccess?.()
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { updateSpecies: mutateAsync, isLoading, isSuccess, error }
}
