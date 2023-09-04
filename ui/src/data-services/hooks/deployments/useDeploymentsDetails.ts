import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  DeploymentDetails,
  ServerDeploymentDetails,
} from 'data-services/models/deployment-details'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

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
  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<DeploymentDetails>({
      queryKey: [API_ROUTES.DEPLOYMENTS, id],
      url: `${API_URL}/${API_ROUTES.DEPLOYMENTS}/${id}/`,
    })

  const deployment = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    deployment,
    isLoading,
    isFetching,
    error,
  }
}
