import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useAddMember = (projectId: string) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: ({ email, roleId }: { email: string; roleId: string }) =>
      axios.post(
        `${API_URL}/${API_ROUTES.MEMBERS(projectId)}/`,
        {
          role_id: roleId,
          email,
        },
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.MEMBERS(projectId)])
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { addMember: mutateAsync, error, isLoading, isSuccess, reset }
}
