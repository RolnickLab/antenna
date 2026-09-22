import { useEffect, useState } from 'react'

/** A row the picker can offer. Only the id decides whether a tick still stands. */
type OfferedCandidate = { id: string }

/**
 * The ticked ids the given candidates still offer.
 *
 * Returns the ids unchanged when all of them survive, so a caller holding the
 * result in state re-renders only when something was really dropped.
 */
export const keepOfferedIds = (
  selectedIds: string[],
  candidates: OfferedCandidate[]
): string[] => {
  const offered = selectedIds.filter((id) =>
    candidates.some((candidate) => candidate.id === id)
  )

  return offered.length === selectedIds.length ? selectedIds : offered
}

/**
 * The merge candidates a reviewer has ticked, kept across a change of search scope.
 *
 * Widening keeps every tick; narrowing drops the rows it stops offering, since
 * merging an occurrence the reviewer cannot see would be unsafe. Only an arrived
 * list says which rows those are, so a list still being fetched prunes nothing.
 */
export const useMergeSelection = ({
  candidates,
  isLoading,
}: {
  candidates: OfferedCandidate[]
  /** True while the candidates are in flight, when they cannot say what is offered. */
  isLoading?: boolean
}): {
  clear: () => void
  selectedIds: string[]
  toggle: (id: string) => void
} => {
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  useEffect(() => {
    if (isLoading) {
      return
    }

    setSelectedIds((ids) => keepOfferedIds(ids, candidates))
  }, [candidates, isLoading])

  return {
    clear: () => setSelectedIds([]),
    selectedIds,
    toggle: (id: string) =>
      setSelectedIds((ids) =>
        ids.includes(id) ? ids.filter((other) => other !== id) : [...ids, id]
      ),
  }
}
