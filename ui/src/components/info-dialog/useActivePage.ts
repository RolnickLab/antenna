import { useSearchParams } from 'react-router-dom'

const SEARCH_PARAM_KEY = 'page'

export const useActivePage = () => {
  const [searchParams, setSearchParams] = useSearchParams()

  const activePage = searchParams.get(SEARCH_PARAM_KEY) ?? undefined

  const setActivePage = (pageSlug?: string) => {
    searchParams.delete(SEARCH_PARAM_KEY)
    if (pageSlug?.length) {
      searchParams.set(SEARCH_PARAM_KEY, pageSlug)
    }
    setSearchParams(searchParams)
  }

  return { activePage, setActivePage }
}
