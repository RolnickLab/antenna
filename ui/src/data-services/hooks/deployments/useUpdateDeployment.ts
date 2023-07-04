import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { DeploymentFieldValues } from 'data-services/models/deployment-details'
import { COLLECTION } from './constants'

const convertToServerFieldValues = (fieldValues: DeploymentFieldValues) => ({
  data_source: fieldValues.path,
  name: fieldValues.name,
  latitude: fieldValues.latitude,
  longitude: fieldValues.longitude,
})

export const useUpdateDeployment = (id: string) => {
  const queryClient = useQueryClient()

  const { mutate, isLoading, isError, isSuccess } = useMutation({
    mutationFn: (fieldValues: DeploymentFieldValues) =>
      axios.patch(
        `${API_URL}/${COLLECTION}/${id}/`,
        convertToServerFieldValues(fieldValues)
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([COLLECTION])
    },
  })

  return { updateDeployment: mutate, isLoading, isError, isSuccess }
}
