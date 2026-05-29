import { useSearchParams } from 'react-router-dom'

const SEARCH_PARAM_KEY = 'capture'

export const useActiveCaptureId = (defaultValue?: string) => {
  const [searchParams, setSearchParams] = useSearchParams()

  const activeCaptureId = searchParams.get(SEARCH_PARAM_KEY) ?? defaultValue

  const setActiveCaptureId = (captureId: string) => {
    searchParams.delete(SEARCH_PARAM_KEY)
    searchParams.set(SEARCH_PARAM_KEY, captureId)
    setSearchParams(searchParams, { replace: true })
  }

  return { activeCaptureId, setActiveCaptureId }
}
