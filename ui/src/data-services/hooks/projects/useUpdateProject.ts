import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

const SUCCESS_TIMEOUT = 1000 // Reset success after 1 second

export const useUpdateProject = (id: string) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: (fieldValues: any) =>
      axios.patch(
        `${API_URL}/${API_ROUTES.PROJECTS}/${id}/`,
        {
          name: fieldValues.name,
          description: fieldValues.description,
        },
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.PROJECTS])
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { updateProject: mutateAsync, isLoading, isSuccess, error }
}
