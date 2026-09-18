import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { ServerRegisterPipelinesResponse } from 'data-services/models/processing-service'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

// `projectId` is optional: the row action re-registers a service without one, while the
// new-service dialog passes the project the service was just created for.
export const usePopulateProcessingService = (projectId?: string) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, data, isLoading, isSuccess, error, reset } = useMutation(
    {
      mutationFn: (id: string) =>
        axios.post<ServerRegisterPipelinesResponse>(
          `${API_URL}/${API_ROUTES.PROCESSING_SERVICES}/${id}/register_pipelines/`,
          undefined,
          {
            headers: getAuthHeader(user),
            params: projectId ? { project_id: projectId } : undefined,
          }
        ),
      onSuccess: () => {
        // Registration creates pipelines and algorithms, so both lists must refetch.
        queryClient.invalidateQueries([API_ROUTES.PROCESSING_SERVICES])
        queryClient.invalidateQueries([API_ROUTES.PIPELINES])
      },
    }
  )

  return {
    populateProcessingService: mutateAsync,
    result: data?.data,
    isLoading,
    isSuccess,
    error,
    reset,
  }
}
