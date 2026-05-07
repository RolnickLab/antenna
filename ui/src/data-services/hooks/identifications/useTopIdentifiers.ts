import { API_ROUTES, API_URL } from 'data-services/constants'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

interface Response {
  project_id?: number
  top_identifiers: {
    id: number
    name?: string
    email: string
    image?: string
    identification_count: number
  }[]
}

export const useTopIdentifiers = (projectId?: string) => {
  const url = `${API_URL}/${API_ROUTES.USERS}/${API_ROUTES.IDENTIFICATIONS}/top/`

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<Response>({
    queryKey: [API_ROUTES.IDENTIFICATIONS, 'top', projectId],
    url: projectId ? `${url}?project_id=${projectId}` : url,
  })

  return {
    data,
    isLoading,
    isFetching,
    error,
  }
}
