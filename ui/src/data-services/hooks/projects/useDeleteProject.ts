import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useDeleteProject = (onSuccess?: () => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, error } = useMutation({
    mutationFn: (id: string) =>
      axios.delete(`${API_URL}/${API_ROUTES.PROJECTS}/${id}/`, {
        headers: getAuthHeader(user),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.PROJECTS])
      onSuccess?.()
    },
  })

  return { deleteProject: mutateAsync, isLoading, isSuccess, error }
}
