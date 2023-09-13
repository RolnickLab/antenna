import { API_ROUTES, API_URL } from 'data-services/constants'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'
import { PageDetails } from './types'

export const usePageDetails = (
  slug: string
): {
  page?: PageDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<PageDetails>({
      queryKey: [API_ROUTES.PAGES, slug],
      url: `${API_URL}/${API_ROUTES.PAGES}/${slug}/`,
    })

  return {
    page: data,
    isLoading,
    isFetching,
    error,
  }
}
