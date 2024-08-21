import { useSearchParams } from 'react-router-dom'

const SEARCH_PARAM_KEY = 'info-page'

export const useActiveInfoPage = () => {
  const [searchParams, setSearchParams] = useSearchParams()

  const activeInfoPage = searchParams.get(SEARCH_PARAM_KEY) ?? undefined

  const setActiveInfoPage = (pageSlug?: string) => {
    searchParams.delete(SEARCH_PARAM_KEY)
    if (pageSlug?.length) {
      searchParams.set(SEARCH_PARAM_KEY, pageSlug)
    }
    setSearchParams(searchParams)
  }

  return { activeInfoPage, setActiveInfoPage }
}
