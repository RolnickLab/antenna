import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { Deployment, ServerDeployment } from 'data-services/models/deployment'
import { getFetchUrl } from 'data-services/utils'

const COLLECTION = 'deployments'

const convertServerRecord = (record: ServerDeployment) => new Deployment(record)

export const useDeployments = (): {
  deployments?: Deployment[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: COLLECTION })

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION],
    queryFn: () =>
      axios
        .get<ServerDeployment[]>(fetchUrl)
        .then((res) => res.data.map(convertServerRecord)),
  })

  return {
    deployments: data,
    isLoading,
    isFetching,
    error,
  }
}
