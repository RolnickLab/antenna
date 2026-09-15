import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

const SEARCH_PARAM_KEY = 'extend'

/**
 * The occurrence the capture view is adding frames to. Held in the URL so the mode
 * survives stepping between captures and the link can be handed to someone else.
 */
export const useExtendOccurrenceId = () => {
  const [searchParams, setSearchParams] = useSearchParams()

  const extendOccurrenceId = searchParams.get(SEARCH_PARAM_KEY) ?? undefined

  const setExtendOccurrenceId = useCallback(
    (occurrenceId?: string) => {
      searchParams.delete(SEARCH_PARAM_KEY)

      if (occurrenceId) {
        searchParams.set(SEARCH_PARAM_KEY, occurrenceId)
      }

      setSearchParams(searchParams, { replace: true })
    },
    [searchParams, setSearchParams]
  )

  return { extendOccurrenceId, setExtendOccurrenceId }
}
