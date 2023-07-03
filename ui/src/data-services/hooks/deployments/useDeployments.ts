import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { Deployment, ServerDeployment } from 'data-services/models/deployment'
import { COLLECTION } from './constants'

const convertServerRecord = (record: ServerDeployment) => new Deployment(record)

export const useDeployments = (): {
  deployments?: Deployment[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION],
    queryFn: () =>
      axios
        .get<{ results: ServerDeployment[] }>(`${API_URL}/${COLLECTION}`)
        .then((res) => res.data.results.map(convertServerRecord)),
  })

  return {
    deployments: data,
    isLoading,
    isFetching,
    error,
  }
}
