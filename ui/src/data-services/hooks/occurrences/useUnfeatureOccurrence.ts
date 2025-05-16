import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useUnfeatureOccurrence = (id: string, onSuccess?: () => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, error } = useMutation({
    mutationFn: () =>
      axios.delete(`${API_URL}/${API_ROUTES.OCCURRENCES}/${id}/feature/`, {
        headers: getAuthHeader(user),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.OCCURRENCES])
      queryClient.invalidateQueries([API_ROUTES.SPECIES])
      onSuccess?.()
    },
  })

  return {
    error,
    unfeatureOccurrence: mutateAsync,
    isLoading,
    isSuccess,
  }
}
