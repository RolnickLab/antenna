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
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.SESSIONS, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerEvent[]
    count: number
  }>({
    queryKey: [API_ROUTES.SESSIONS, params],
    url: fetchUrl,
  })

  const sessions = useMemo(() => data?.results.map(convertServerRecord), [data])

  return {
    sessions,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
