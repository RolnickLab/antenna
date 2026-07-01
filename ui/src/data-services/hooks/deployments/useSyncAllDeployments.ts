import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useSyncAllDeployments = () => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, reset, isLoading, isSuccess, error, data } = useMutation(
    {
      mutationFn: (projectId: string) =>
        axios.post<{ job_ids: number[]; queued: number; project_id: number }>(
          `${API_URL}/${API_ROUTES.DEPLOYMENTS}/sync-all/?project_id=${projectId}`,
          undefined,
          {
            headers: getAuthHeader(user),
          }
        ),
      onSuccess: (resp) => {
        queryClient.invalidateQueries([API_ROUTES.JOBS])
        queryClient.invalidateQueries([API_ROUTES.CAPTURES])
        queryClient.invalidateQueries([API_ROUTES.DEPLOYMENTS])

        return resp.data
      },
    }
  )

  return {
    syncAllDeployments: mutateAsync,
    reset,
    isLoading,
    isSuccess,
    error,
    data,
  }
}
