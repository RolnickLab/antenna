import { Capture } from 'data-services/models/capture'
import { useEffect, useState } from 'react'
import { useActiveOccurrences } from './useActiveOccurrences'

export const useActiveCapture = (captures: Capture[]) => {
  const [activeCapture, setActiveCapture] = useState<Capture>()
  const { activeOccurrences } = useActiveOccurrences()

  useEffect(() => {
    // On load, decide what first capture to select
    if (!activeCapture && captures.length) {
      let firstCapture: Capture | undefined

      // If we have one occurrence selected, search for the frame where it appears for the first time
      if (activeOccurrences.length === 1) {
        const activeOccurrence = activeOccurrences[0]
        firstCapture = captures.find((c) =>
          c.detections.find((d) => d.occurrenceId === activeOccurrence)
        )
      }

      // Fallback to first capture
      setActiveCapture(firstCapture ?? captures[0])
    }
  }, [captures])

  return { activeCapture, setActiveCapture }
}
