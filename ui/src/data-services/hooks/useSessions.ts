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
        .get<ServerEvent[]>(fetchUrl)
        .then((res) => res.data.map(convertServerRecord)),
  })

  return {
    sessions: data,
    total: data?.length ?? 0, // TODO: Until we get total in response
    isLoading,
    isFetching,
    error,
  }
}
