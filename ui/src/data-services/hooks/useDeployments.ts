import { Deployment, ServerDeployment } from 'data-services/models/deployment'
import { useGetList } from './useGetList'

const convertServerRecord = (record: ServerDeployment) => new Deployment(record)

export const useDeployments = (): {
  deployments: Deployment[]
  isLoading: boolean
} => {
  const { data, isLoading } = useGetList<ServerDeployment, Deployment>(
    { collection: 'deployments' },
    convertServerRecord
  )

  return {
    deployments: data,
    isLoading,
  }
}
