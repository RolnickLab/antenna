import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { Capture, ServerCapture } from 'data-services/models/capture'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'

const COLLECTION = 'captures'

const convertServerRecord = (record: ServerCapture) => new Capture(record)

const FETCH_PARAMS: FetchParams = {
  pagination: { page: 0, perPage: 10000 },
  sort: { field: 'timestamp', order: 'asc' },
}

export const useCaptures = (
  sessionId: string
): {
  captures?: Capture[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({
    collection: COLLECTION,
    params: {
      ...FETCH_PARAMS,
      filters: [{ field: 'event', value: sessionId }],
    },
  })

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, { event: sessionId, ...FETCH_PARAMS }],
    queryFn: () =>
      axios
        .get<{ results: ServerCapture[]; count: number }>(fetchUrl)
        .then((res) => ({
          results: res.data.results.map(convertServerRecord),
          count: res.data.count,
        })),
  })

  return {
    captures: data?.results,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
