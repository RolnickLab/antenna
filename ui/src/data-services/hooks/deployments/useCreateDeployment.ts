import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { DeploymentFieldValues } from 'data-services/models/deployment-details'
import { getAuthHeader } from 'data-services/utils'

import { useUser } from 'utils/user/userContext'

const convertToServerFieldValues = (fieldValues: DeploymentFieldValues) => ({
  data_source: fieldValues.path,
  description: fieldValues.description,
  events: [],
  name: fieldValues.name,
  latitude: fieldValues.latitude,
  longitude: fieldValues.longitude,
  occurrences: [],
  project: null,
})

export const useCreateDeployment = () => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, error } = useMutation({
    mutationFn: (fieldValues: DeploymentFieldValues) =>
      axios.post(
        `${API_URL}/${API_ROUTES.DEPLOYMENTS}/`,
        convertToServerFieldValues(fieldValues),
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.DEPLOYMENTS])
    },
  })

  return { createDeployment: mutateAsync, isLoading, error }
}
