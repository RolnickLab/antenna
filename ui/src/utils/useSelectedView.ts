import { useSearchParams } from 'react-router-dom'

const SEARCH_PARAM_KEY_VIEW = 'view'

export const useSelectedView = (
  defaultValue: string,
  key: string = SEARCH_PARAM_KEY_VIEW
) => {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedView = searchParams.get(key) ?? undefined

  const setSelectedView = (selectedView?: string) => {
    searchParams.delete(key)

    if (selectedView && selectedView !== defaultValue) {
      searchParams.set(key, selectedView ?? defaultValue)
    }

    setSearchParams(searchParams)
  }

  return {
    selectedView: selectedView ?? defaultValue,
    setSelectedView,
  }
}
