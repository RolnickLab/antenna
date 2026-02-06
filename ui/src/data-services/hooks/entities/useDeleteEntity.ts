import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useDeleteEntity = ({
  collection,
  onSuccess,
  projectId,
}: {
  collection: string
  onSuccess?: () => void
  projectId: string
}) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, error } = useMutation({
    mutationFn: (id: string) =>
      axios.delete(`${API_URL}/${collection}/${id}/?project_id=${projectId}`, {
        headers: getAuthHeader(user),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries([collection])
      onSuccess?.()
    },
  })

  return { deleteEntity: mutateAsync, isLoading, isSuccess, error }
}
