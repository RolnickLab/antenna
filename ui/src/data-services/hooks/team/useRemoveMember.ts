import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useRemoveMember = (projectId: string) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: (id: string) =>
      axios.delete(`${API_URL}/${API_ROUTES.MEMBERS(projectId)}/${id}/`, {
        headers: getAuthHeader(user),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.MEMBERS(projectId)])
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { removeMember: mutateAsync, isLoading, error, isSuccess }
}
