import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useAddMember = () => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: ({
      email,
      projectId,
      roleId,
    }: {
      email: string
      projectId: string
      roleId: string
    }) =>
      axios.post(
        `${API_URL}/${API_ROUTES.MEMBERS}/?project_id=${projectId}`,
        {
          role_id: roleId,
          email,
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

  return { addMember: mutateAsync, isLoading, error, isSuccess }
}
