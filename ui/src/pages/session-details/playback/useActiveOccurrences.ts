import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

const SEARCH_PARAM_KEY = 'occurrence'

export const useActiveOccurrences = () => {
  const [searchParams, setSearchParams] = useSearchParams()

  const activeOccurrences = searchParams.getAll(SEARCH_PARAM_KEY)

  const setActiveOccurrences = useCallback(
    (occurrences: string[]) => {
      searchParams.delete(SEARCH_PARAM_KEY)
      occurrences.forEach((o) => searchParams.append(SEARCH_PARAM_KEY, o))
      setSearchParams(searchParams)
    },
    [searchParams, setSearchParams]
  )

  return { activeOccurrences, setActiveOccurrences }
}
