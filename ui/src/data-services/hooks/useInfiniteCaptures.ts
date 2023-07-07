import { useInfiniteQuery } from '@tanstack/react-query'
import axios from 'axios'
import { Capture, ServerCapture } from 'data-services/models/capture'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'

const COLLECTION = 'captures'

const convertServerRecord = (record: ServerCapture) => new Capture(record)

const PER_PAGE = 20

const fetchCaptures = async (sessionId: string, page: number) => {
  const fetchUrl = getFetchUrl({
    collection: COLLECTION,
    params: {
      pagination: { page, perPage: PER_PAGE },
      filters: [{ field: 'event', value: sessionId }],
    },
  })

  const res = await axios.get<{ results: ServerCapture[]; count: number }>(
    fetchUrl
  )

  return {
    results: res.data.results.map(convertServerRecord),
    count: res.data.count,
    page,
  }
}

export const useInfiniteCaptures = (sessionId: string, offset?: number) => {
  const queryKey = [COLLECTION, { event: sessionId }]
  const startPage = offset !== undefined ? Math.floor(offset / PER_PAGE) : 0

  const {
    data,
    fetchNextPage,
    fetchPreviousPage,
    isFetchingNextPage,
    isFetchingPreviousPage,
    hasNextPage,
    hasPreviousPage,
  } = useInfiniteQuery(
    queryKey,
    ({ pageParam = startPage }) => fetchCaptures(sessionId, pageParam),
    {
      getNextPageParam: (lastPage) => {
        if ((lastPage.page + 1) * PER_PAGE >= lastPage.count) {
          return undefined
        }

        return lastPage.page + 1
      },
      getPreviousPageParam: (firstPage) => {
        if (firstPage.page === 0) {
          return undefined
        }

        return firstPage.page - 1
      },
    }
  )

  const captures = useMemo(
    () => data?.pages.map((page) => page.results).flat(1),
    [data]
  )

  return {
    captures,
    fetchNextPage,
    fetchPreviousPage,
    isFetchingNextPage,
    isFetchingPreviousPage,
    hasNextPage,
    hasPreviousPage,
  }
}
