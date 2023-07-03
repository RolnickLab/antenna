import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import {
  DeploymentDetails,
  ServerDeploymentDetails,
} from 'data-services/models/deployment-details'
import { COLLECTION } from './constants'

const convertServerRecord = (record: ServerDeploymentDetails) =>
  new DeploymentDetails(record)

export const useDeploymentDetails = (
  id: string
): {
  deployment?: DeploymentDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, id],
    queryFn: () =>
      axios
        .get<DeploymentDetails>(`${API_URL}/${COLLECTION}/${id}`)
        .then((res) => convertServerRecord(res.data)),
  })

  return {
    deployment: data,
    isLoading,
    isFetching,
    error,
  }
}
