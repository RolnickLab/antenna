import { API_ROUTES, API_URL } from 'data-services/constants'
import { useAuthorizedQuery } from './useAuthorizedQuery'

export const useMe = () => {
  const { data, isLoading, error } = useAuthorizedQuery<{
    id: string
    email: string
    name?: string
  }>({
    queryKey: [API_ROUTES.ME],
    url: `${API_URL}/${API_ROUTES.ME}/`,
  })

  return { user: data, isLoading, error }
}
