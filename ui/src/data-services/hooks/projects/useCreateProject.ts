import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useCreateProject = () => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, error } = useMutation({
    mutationFn: (fieldValues: any) =>
      axios.post(
        `${API_URL}/${API_ROUTES.PROJECTS}/`,
        {
          name: fieldValues.name,
          description: fieldValues.description,
        },
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: () => queryClient.invalidateQueries([API_ROUTES.PROJECTS]),
  })

  return { createProject: mutateAsync, isLoading, isSuccess, error }
}
