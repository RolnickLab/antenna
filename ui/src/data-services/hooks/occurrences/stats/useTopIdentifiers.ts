import { API_ROUTES, API_URL } from 'data-services/constants'
import { useAuthorizedQuery } from '../../auth/useAuthorizedQuery'

interface TopIdentifier {
  id: number
  name?: string
  image?: string
  identification_count: number
}

interface Response {
  count: number
  next: string | null
  previous: string | null
  results: TopIdentifier[]
}

export const useTopIdentifiers = (projectId?: string, limit = 5) => {
  const url = `${API_URL}/${API_ROUTES.OCCURRENCES}/stats/top-identifiers/`

  const params = new URLSearchParams()
  if (projectId) params.set('project_id', projectId)
  params.set('limit', String(limit))

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<Response>({
    queryKey: [
      API_ROUTES.OCCURRENCES,
      'stats',
      'top-identifiers',
      projectId,
      limit,
    ],
    url: `${url}?${params.toString()}`,
  })

  return {
    data,
    isLoading,
    isFetching,
    error,
  }
}
