import { useSearchParams } from 'react-router-dom'
import { SEARCH_PARAM_KEY_PAGE } from './usePagination'

const SEARCH_PARAM_KEY_SEARCH = 'search'

export const useSearch = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const search = searchParams.get(SEARCH_PARAM_KEY_SEARCH) ?? ''

  const setSearch = (search: string) => {
    // New results start from the first page.
    searchParams.delete(SEARCH_PARAM_KEY_PAGE)
    searchParams.delete(SEARCH_PARAM_KEY_SEARCH)

    if (search.length) {
      searchParams.set(SEARCH_PARAM_KEY_SEARCH, search)
    }

    setSearchParams(searchParams)
  }

  return { search, setSearch }
}
