import { API_ROUTES } from 'data-services/constants'
import { Collection, ServerCollection } from 'data-services/models/collection'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { UserPermission } from 'utils/user/types'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const REFETCH_INTERVAL = 10000 // Refetch every 10 second

const convertServerRecord = (record: ServerCollection) => new Collection(record)

export const useCollections = (
  params: FetchParams | undefined,
  refetchInterval = REFETCH_INTERVAL
): {
  collections?: Collection[]
  total: number
  userPermissions?: UserPermission[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.COLLECTIONS, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerCollection[]
    user_permissions?: UserPermission[]
    count: number
  }>({
    queryKey: [API_ROUTES.COLLECTIONS, params],
    url: fetchUrl,
    refetchInterval,
  })

  const collections = useMemo(
    () => data?.results.map(convertServerRecord),
    [data]
  )

  return {
    collections,
    total: data?.count ?? 0,
    userPermissions: data?.user_permissions,
    isLoading,
    isFetching,
    error,
  }
}
