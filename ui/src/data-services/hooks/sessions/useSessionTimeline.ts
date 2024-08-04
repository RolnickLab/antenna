import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  ServerTimelineTick,
  TimelineTick,
} from 'data-services/models/timeline-tick'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

export const useSessionTimeline = (
  id: string
): {
  timeline?: TimelineTick[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    data: ServerTimelineTick[]
  }>({
    queryKey: [API_ROUTES.SESSIONS, id, 'timeline'],
    url: `${API_URL}/${API_ROUTES.SESSIONS}/${id}/timeline/`,
  })

  const timeline = useMemo(
    () => data?.data.map((record) => new TimelineTick(record)),
    [data]
  )

  return {
    timeline,
    isLoading,
    isFetching,
    error,
  }
}
