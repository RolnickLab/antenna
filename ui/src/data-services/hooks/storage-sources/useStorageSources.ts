import { API_ROUTES } from 'data-services/constants'
import { ServerStorage, StorageSource } from 'data-services/models/storage'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { UserPermission } from 'utils/user/types'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerStorage) => new StorageSource(record)

export const useStorageSources = (
  params?: FetchParams
): {
  items?: StorageSource[]
  total: number
  userPermissions?: UserPermission[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.STORAGE, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerStorage[]
    user_permissions?: UserPermission[]
    count: number
  }>({
    queryKey: [API_ROUTES.STORAGE, params],
    url: fetchUrl,
  })

  const items = useMemo(
    () => data?.results.map(convertServerRecord),
    [data]
  )

  return {
    items,
    total: data?.count ?? 0,
    userPermissions: data?.user_permissions,
    isLoading,
    isFetching,
    error,
  }
}
