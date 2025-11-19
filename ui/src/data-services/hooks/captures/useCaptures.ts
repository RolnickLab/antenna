import { API_ROUTES, REFETCH_INTERVAL } from 'data-services/constants'
import { Capture, ServerCapture } from 'data-services/models/capture'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { UserPermission } from 'utils/user/types'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerCapture) => new Capture(record)

export const useCaptures = (
  params: FetchParams
): {
  captures?: Capture[]
  userPermissions?: UserPermission[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.CAPTURES, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerCapture[]
    user_permissions?: UserPermission[]
    count: number
  }>({
    queryKey: [API_ROUTES.CAPTURES, params],
    url: fetchUrl,
    refetchInterval: REFETCH_INTERVAL,
  })

  const captures = useMemo(() => data?.results.map(convertServerRecord), [data])

  return {
    captures,
    userPermissions: data?.user_permissions,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
