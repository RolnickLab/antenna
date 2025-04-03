import { API_ROUTES, API_URL } from 'data-services/constants'
import { Algorithm, ServerAlgorithm } from 'data-services/models/algorithm'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerAlgorithm) => new Algorithm(record)

export const useAlgorithmDetails = (
  algorithmId: string
): {
  algorithm?: Algorithm
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<Algorithm>({
    queryKey: [API_ROUTES.ALGORITHM, algorithmId],
    url: `${API_URL}/${API_ROUTES.ALGORITHM}/${algorithmId}/`,
  })

  const algorithm = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    algorithm,
    isLoading,
    isFetching,
    error,
  }
}
