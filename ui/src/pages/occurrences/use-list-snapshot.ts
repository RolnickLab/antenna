import { useState } from 'react'

// Returns the list order as it was when first loaded for this key. A background refetch
// can reorder the list (a confirmed occurrence jumps to the top of "recently updated"),
// which would otherwise send Previous somewhere other than the item just left.
// Without a key the live list is returned as is and nothing is copied.
export const useListSnapshot = (
  items: { id: string }[] | undefined,
  listKey: string | undefined
) => {
  const [snapshot, setSnapshot] = useState<{
    items: { id: string }[]
    listKey: string
  }>()

  if (listKey === undefined) {
    return items
  }

  if (items && snapshot?.listKey !== listKey) {
    setSnapshot({ items: items.map(({ id }) => ({ id })), listKey })
  }

  return snapshot?.listKey === listKey ? snapshot.items : items
}
