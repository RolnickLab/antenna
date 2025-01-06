import { API_ROUTES } from 'data-services/constants'
import { Algorithm, ServerAlgorithm } from 'data-services/models/algorithm'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { UserPermission } from 'utils/user/types'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerAlgorithm) => new Algorithm(record)

export const useAlgorithms = (
  params: FetchParams | undefined
): {
  algorithms?: Algorithm[]
  total: number
  userPermissions?: UserPermission[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.ALGORITHM, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerAlgorithm[]
    user_permissions?: UserPermission[]
    count: number
  }>({
    queryKey: [API_ROUTES.ALGORITHM, params],
    url: fetchUrl,
  })

  const algorithms = useMemo(
    () => data?.results.map(convertServerRecord),
    [data]
  )

  return {
    algorithms,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
