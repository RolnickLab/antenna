import { API_ROUTES } from 'data-services/constants'
import {
  ProcessingService,
  ServerProcessingService,
} from 'data-services/models/processing-service'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { UserPermission } from 'utils/user/types'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerProcessingService) =>
  new ProcessingService(record)

export const useProcessingServices = (
  params?: FetchParams
): {
  items?: ProcessingService[]
  total: number
  userPermissions?: UserPermission[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({
    collection: API_ROUTES.PROCESSING_SERVICES,
    params,
  })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ProcessingService[]
    user_permissions?: UserPermission[]
    count: number
  }>({
    queryKey: [API_ROUTES.PROCESSING_SERVICES, params],
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
