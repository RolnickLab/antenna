import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { ServerEvent, Session } from '../models/session'

const COLLECTION = 'events'

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
  const fetchUrl = getFetchUrl({ collection: COLLECTION, params })

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, params],
    queryFn: () =>
      axios
        .get<{ results: ServerEvent[]; count: number }>(fetchUrl)
        .then((res) => ({
          results: res.data.results.map(convertServerRecord),
          count: res.data.count,
        })),
  })

  return {
    sessions: data?.results,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
