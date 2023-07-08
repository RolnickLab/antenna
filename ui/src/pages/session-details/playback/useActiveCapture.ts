import { Capture } from 'data-services/models/capture'
import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useActiveOccurrences } from './useActiveOccurrences'

const SEARCH_PARAM_KEY = 'capture'

export const useActiveCaptureId = () => {
  const [searchParams, setSearchParams] = useSearchParams()

  const activeCaptureId = searchParams.get(SEARCH_PARAM_KEY) ?? undefined

  const setActiveCaptureId = (captureId: string) => {
    searchParams.delete(SEARCH_PARAM_KEY)
    searchParams.set(SEARCH_PARAM_KEY, captureId)
    setSearchParams(searchParams)
  }

  return { activeCaptureId, setActiveCaptureId }
}

export const useActiveCapture = (captures: Capture[]) => {
  const { activeCaptureId, setActiveCaptureId } = useActiveCaptureId()
  const { activeOccurrences } = useActiveOccurrences()
  const activeCapture = captures.find(
    (capture) => capture.id === activeCaptureId
  )
  const setActiveCapture = (capture: Capture) => {
    setActiveCaptureId(capture.id)
  }

  useEffect(() => {
    // On load, decide what first capture to select
    if (!activeCapture && captures.length) {
      let firstCapture: Capture | undefined

      // If we have an occurrence selected, search for the frame where it appears for the first time
      if (activeOccurrences.length === 1) {
        firstCapture = captures.find((c) =>
          c.detections.find((d) => d.occurrenceId === activeOccurrences[0])
        )
      }

      // Fallback to first capture
      setActiveCapture(firstCapture ?? captures[0])
    }
  }, [captures, activeCapture])

  return { activeCapture, setActiveCapture }
}
