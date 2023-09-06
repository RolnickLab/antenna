import { API_ROUTES } from 'data-services/constants'
import { getFetchUrl } from 'data-services/utils'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'
import { Page } from './types'

export const usePages = (): {
  pages?: Page[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.PAGES })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: Page[]
  }>({
    queryKey: [API_ROUTES.PAGES],
    url: fetchUrl,
  })

  return {
    pages: data?.results,
    isLoading,
    isFetching,
    error,
  }
}
