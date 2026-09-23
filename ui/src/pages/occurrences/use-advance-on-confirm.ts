import { useCallback, useEffect, useRef } from 'react'
import { getAdjacentIds } from './adjacent-occurrences'

// Returns a handler for a finished confirm that moves to the next item, or closes
// after the last one. A confirm that lands after the user has moved on is ignored.
export const useAdvanceOnConfirm = ({
  close,
  currentId,
  goTo,
  items,
}: {
  close: () => void
  currentId: string
  goTo: (id: string) => void
  items?: { id: string }[]
}) => {
  const currentIdRef = useRef<string>()
  const latest = useRef({ close, goTo, items })
  latest.current = { close, goTo, items }

  useEffect(() => {
    currentIdRef.current = currentId

    return () => {
      currentIdRef.current = undefined
    }
  }, [currentId])

  return useCallback((confirmedId: string) => {
    if (confirmedId !== currentIdRef.current) {
      return
    }
    const { nextId } = getAdjacentIds(latest.current.items, confirmedId)
    if (nextId) {
      latest.current.goTo(nextId)
    } else {
      latest.current.close()
    }
  }, [])
}
