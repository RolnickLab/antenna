import { useSearchParams } from 'react-router-dom'

// Same key as the list views' taxon filter, so a link into a session keeps the taxon.
const SEARCH_PARAM_KEY = 'taxon'

export const useActiveTaxonId = () => {
  const [searchParams, setSearchParams] = useSearchParams()

  const activeTaxonId = searchParams.get(SEARCH_PARAM_KEY) ?? undefined

  const setActiveTaxonId = (taxonId?: string) => {
    searchParams.delete(SEARCH_PARAM_KEY)
    if (taxonId) {
      searchParams.set(SEARCH_PARAM_KEY, taxonId)
    }
    setSearchParams(searchParams, { replace: true })
  }

  return { activeTaxonId, setActiveTaxonId }
}
