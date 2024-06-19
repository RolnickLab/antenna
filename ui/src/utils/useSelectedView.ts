import { useSearchParams } from 'react-router-dom'

const SEARCH_PARAM_KEY_VIEW = 'view'

export const useSelectedView = (defaultValue: string) => {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedView = searchParams.get(SEARCH_PARAM_KEY_VIEW) ?? undefined

  const setSelectedView = (selectedView: string | null) => {
    searchParams.delete(SEARCH_PARAM_KEY_VIEW)

    if (selectedView && selectedView !== defaultValue) {
      searchParams.set(SEARCH_PARAM_KEY_VIEW, selectedView)
    }

    setSearchParams(searchParams)
  }

  return {
    selectedView: selectedView ?? defaultValue,
    setSelectedView,
  }
}
