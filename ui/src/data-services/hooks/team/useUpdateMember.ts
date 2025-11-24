import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useUpdateMember = (id: string) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: ({
      projectId,
      roleId,
    }: {
      projectId: string
      roleId: string
    }) =>
      axios.put(
        `${API_URL}/${API_ROUTES.MEMBERS}/${id}/?project_id=${projectId}`,
        {
          role_id: roleId,
        },
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.MEMBERS])
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { updateMember: mutateAsync, isLoading, error, isSuccess }
}
