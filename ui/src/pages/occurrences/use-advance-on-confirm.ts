import { useCallback, useEffect, useRef } from 'react'
import { getAdjacentIds } from './adjacent-occurrences'

// Returns a handler for a finished confirm that moves to the next item, or closes
// after the last one. An unlisted item, or one the user has left, stays put.
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
    const { items } = latest.current
    const { nextId } = getAdjacentIds(items, confirmedId)
    if (nextId) {
      latest.current.goTo(nextId)
    } else if (items?.[items.length - 1]?.id === confirmedId) {
      latest.current.close()
    }
  }, [])
}
