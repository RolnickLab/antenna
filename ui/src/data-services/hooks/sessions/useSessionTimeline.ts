import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  ServerTimelineTick,
  TimelineTick,
} from 'data-services/models/timeline-tick'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

export const useSessionTimeline = (
  id: string,
  params?: { taxon?: string }
): {
  timeline?: TimelineTick[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const taxon = params?.taxon
  const url = `${API_URL}/${API_ROUTES.SESSIONS}/${id}/timeline/${
    taxon ? `?taxon=${taxon}` : ''
  }`

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    data: ServerTimelineTick[]
  }>({
    queryKey: [API_ROUTES.SESSIONS, id, 'timeline', taxon],
    url,
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
