import { API_ROUTES } from 'data-services/constants'
import { Backend, ServerBackend } from 'data-services/models/backend'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { UserPermission } from 'utils/user/types'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerBackend) => new Backend(record)

export const useBackends = (
  params?: FetchParams
): {
  items?: Backend[]
  total: number
  userPermissions?: UserPermission[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.BACKENDS, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: Backend[]
    user_permissions?: UserPermission[]
    count: number
  }>({
    queryKey: [API_ROUTES.BACKENDS, params],
    url: fetchUrl,
  })

  const items = useMemo(() => data?.results.map(convertServerRecord), [data])

  return {
    items,
    total: data?.count ?? 0,
    userPermissions: data?.user_permissions,
    isLoading,
    isFetching,
    error,
  }
}
