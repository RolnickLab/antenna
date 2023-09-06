import { useInfiniteQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES } from 'data-services/constants'
import { Capture, ServerCapture } from 'data-services/models/capture'
import { getAuthHeader, getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { User } from 'utils/user/types'
import { useUser } from 'utils/user/userContext'

const PER_PAGE = 200

const convertServerRecord = (record: ServerCapture) => new Capture(record)

const fetchCaptures = async (sessionId: string, page: number, user: User) => {
  const fetchUrl = getFetchUrl({
    collection: API_ROUTES.CAPTURES,
    params: {
      pagination: { page, perPage: PER_PAGE },
      sort: { field: 'timestamp', order: 'asc' },
      filters: [{ field: 'event', value: sessionId }],
    },
  })

  const res = await axios.get<{ results: ServerCapture[]; count: number }>(
    fetchUrl,
    { headers: getAuthHeader(user) }
  )

  return {
    results: res.data.results.map(convertServerRecord),
    count: res.data.count,
    page,
  }
}

export const useInfiniteCaptures = (sessionId: string, offset?: number) => {
  const { user } = useUser()
  const queryKey = [API_ROUTES.CAPTURES, { event: sessionId }]
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
    ({ pageParam = startPage }) => fetchCaptures(sessionId, pageParam, user),
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
