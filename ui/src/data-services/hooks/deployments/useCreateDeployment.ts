import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { DeploymentFieldValues } from 'data-services/models/deployment-details'
import { COLLECTION } from './constants'

const convertToServerFieldValues = (fieldValues: DeploymentFieldValues) => ({
  data_source: fieldValues.path,
  description: '',
  events: [],
  name: fieldValues.name,
  latitude: fieldValues.latitude,
  longitude: fieldValues.longitude,
  occurrences: [],
  project: null,
})

export const useCreateDeployment = () => {
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, error } = useMutation({
    mutationFn: (fieldValues: DeploymentFieldValues) =>
      axios.post(
        `${API_URL}/${COLLECTION}/`,
        convertToServerFieldValues(fieldValues)
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([COLLECTION])
    },
  })

  return { createDeployment: mutateAsync, isLoading, error }
}
