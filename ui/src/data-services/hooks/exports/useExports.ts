import { API_ROUTES, REFETCH_INTERVAL } from 'data-services/constants'
import { Export, ServerExport } from 'data-services/models/export'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { UserPermission } from 'utils/user/types'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerExport) => new Export(record)

export const useExports = (
  params?: FetchParams,
  poll?: boolean
): {
  error?: unknown
  exports?: Export[]
  isFetching: boolean
  isLoading: boolean
  total: number
  userPermissions?: UserPermission[]
} => {
  const fetchUrl = getFetchUrl({
    collection: API_ROUTES.EXPORTS,
    params,
  })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    count: number
    results: ServerExport[]
    user_permissions?: UserPermission[]
  }>({
    queryKey: [API_ROUTES.EXPORTS, params],
    url: fetchUrl,
    refetchInterval: poll ? REFETCH_INTERVAL : undefined,
  })

  const exports = useMemo(() => data?.results.map(convertServerRecord), [data])

  return {
    error,
    exports,
    isFetching,
    isLoading,
    total: data?.count ?? 0,
    userPermissions: data?.user_permissions,
  }
}
