import { API_ROUTES } from 'data-services/constants'
import { Capture, ServerCapture } from 'data-services/models/capture'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const REFETCH_INTERVAL = 10000 // Refetch every 10 second

const convertServerRecord = (record: ServerCapture) => new Capture(record)

export const useCaptures = (
  params: FetchParams
): {
  captures?: Capture[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.CAPTURES, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerCapture[]
    count: number
  }>({
    queryKey: [API_ROUTES.CAPTURES, params],
    url: fetchUrl,
    refetchInterval: REFETCH_INTERVAL,
  })

  const captures = useMemo(() => data?.results.map(convertServerRecord), [data])

  return {
    captures,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
