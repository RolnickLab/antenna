import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useSyncDeploymentSourceImages = () => {
    const { user } = useUser()
    const queryClient = useQueryClient()

    const { mutateAsync, isLoading, isSuccess, error, data } = useMutation({
        mutationFn: (id: string) =>
            axios.post<{ job_id: number, project_id: number }>(`${API_URL}/${API_ROUTES.DEPLOYMENTS}/${id}/sync/`, undefined, {
                headers: getAuthHeader(user),
            }),
        onSuccess: (resp) => {
            queryClient.invalidateQueries([API_ROUTES.JOBS])
            queryClient.invalidateQueries([API_ROUTES.CAPTURES])

            return resp.data
        },
    })

    return { syncDeploymentSourceImages: mutateAsync, isLoading, isSuccess, error, data }
}
