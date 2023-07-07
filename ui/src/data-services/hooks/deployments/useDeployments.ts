import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { Deployment, ServerDeployment } from 'data-services/models/deployment'
import { getFetchUrl } from 'data-services/utils'
import { COLLECTION } from './constants'

const convertServerRecord = (record: ServerDeployment) => new Deployment(record)

export const useDeployments = (): {
  deployments?: Deployment[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({
    collection: COLLECTION,
    params: { pagination: { page: 0, perPage: 100 } },
  })

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION],
    queryFn: () =>
      axios
        .get<{ results: ServerDeployment[] }>(fetchUrl)
        .then((res) => res.data.results.map(convertServerRecord)),
  })

  return {
    deployments: data,
    isLoading,
    isFetching,
    error,
  }
}
