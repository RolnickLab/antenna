import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

interface GenerateAPIKeyResponse {
  api_key: string
  prefix: string
  message: string
}

export const useGenerateAPIKey = (projectId?: string) => {
  const { user } = useUser()
  const queryClient = useQueryClient()
  const params = projectId ? `?project_id=${projectId}` : ''

  const { mutateAsync, isLoading, isSuccess, error, data } = useMutation({
    mutationFn: (id: string) =>
      axios.post<GenerateAPIKeyResponse>(
        `${API_URL}/${API_ROUTES.PROCESSING_SERVICES}/${id}/generate_key/${params}`,
        undefined,
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.PROCESSING_SERVICES])
    },
  })

  return {
    generateAPIKey: mutateAsync,
    isLoading,
    isSuccess,
    error,
    apiKey: data?.data.api_key,
  }
}
