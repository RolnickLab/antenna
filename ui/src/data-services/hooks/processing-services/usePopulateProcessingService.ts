import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const usePopulateProcessingService = () => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, error } = useMutation({
    mutationFn: (id: string) =>
      axios.post<{ id: number }>(
        `${API_URL}/${API_ROUTES.PROCESSING_SERVICES}/${id}/register_pipelines/`,
        undefined,
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.PROCESSING_SERVICES])
    },
  })

  return { populateProcessingService: mutateAsync, isLoading, isSuccess, error }
}
