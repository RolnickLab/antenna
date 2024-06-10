import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { DeploymentFieldValues } from 'data-services/models/deployment-details'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'
import { convertToFormData } from './utils'

export const useUpdateDeployment = (id: string) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutate, isLoading, error, isSuccess } = useMutation({
    mutationFn: (fieldValues: DeploymentFieldValues) =>
      axios.patch(
        `${API_URL}/${API_ROUTES.DEPLOYMENTS}/${id}/`,
        convertToFormData(fieldValues),
        {
          headers: {
            ...getAuthHeader(user),
            'Content-Type': 'multipart/form-data',
          },
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.DEPLOYMENTS])
    },
  })

  return { updateDeployment: mutate, isLoading, error, isSuccess }
}
