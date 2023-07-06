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
      sort: { field: 'timestamp', order: 'asc' },
      filters: [{ field: 'event', value: sessionId }],
    },
  })

  const res = await axios.get<{ results: ServerCapture[]; count: number }>(
    fetchUrl
  )

  return {
    results: res.data.results.map(convertServerRecord),
    count: res.data.count,
  }
}

export const useInfiniteCaptures = (sessionId: string) => {
  const queryKey = [COLLECTION, { event: sessionId }]

  const { data, hasNextPage, fetchNextPage, isFetchingNextPage } =
    useInfiniteQuery(
      queryKey,
      ({ pageParam = 1 }) => fetchCaptures(sessionId, pageParam - 1),
      {
        getNextPageParam: (lastPage, allPages) => {
          const allItems = allPages.map((page) => page.results).flat(1)

          if (
            allItems.length >= lastPage.count ||
            lastPage.results.length < PER_PAGE
          ) {
            return undefined
          }

          return allPages.length + 1
        },
      }
    )

  const captures = useMemo(
    () => data?.pages.map((page) => page.results).flat(1),
    [data]
  )

  return {
    captures,
    isLoading: isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  }
}
