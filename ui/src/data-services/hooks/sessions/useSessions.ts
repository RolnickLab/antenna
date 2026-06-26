import { API_ROUTES } from 'data-services/constants'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { ServerEvent, Session } from '../../models/session'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerEvent) => new Session(record)

export const useSessions = (
  params?: FetchParams
): {
  sessions?: Session[]
  total: number
  totalIsExact: boolean
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.SESSIONS, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerEvent[]
    count: number
    count_is_exact?: boolean
  }>({
    queryKey: [API_ROUTES.SESSIONS, params],
    url: fetchUrl,
  })

  const sessions = useMemo(() => data?.results.map(convertServerRecord), [data])

  return {
    sessions,
    total: data?.count ?? 0,
    totalIsExact: data?.count_is_exact ?? true,
    isLoading,
    isFetching,
    error,
  }
}
