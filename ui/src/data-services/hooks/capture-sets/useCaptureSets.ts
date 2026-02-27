import { API_ROUTES, REFETCH_INTERVAL } from 'data-services/constants'
import { CaptureSet, ServerCaptureSet } from 'data-services/models/capture-set'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { UserPermission } from 'utils/user/types'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerCaptureSet) => new CaptureSet(record)

export const useCaptureSets = (
  params: FetchParams | undefined,
  poll?: boolean
): {
  captureSets?: CaptureSet[]
  total: number
  userPermissions?: UserPermission[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.CAPTURE_SETS, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerCaptureSet[]
    user_permissions?: UserPermission[]
    count: number
  }>({
    queryKey: [API_ROUTES.CAPTURE_SETS, params],
    url: fetchUrl,
    refetchInterval: poll ? REFETCH_INTERVAL : undefined,
  })

  const captureSets = useMemo(
    () => data?.results.map(convertServerRecord),
    [data]
  )

  return {
    captureSets,
    total: data?.count ?? 0,
    userPermissions: data?.user_permissions,
    isLoading,
    isFetching,
    error,
  }
}
