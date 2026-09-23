import { useState } from 'react'

// Returns the list order as it was when first loaded for this key. A background refetch
// can reorder the list (a confirmed occurrence jumps to the top of "recently updated"),
// which would otherwise send Previous somewhere other than the item just left.
export const useListSnapshot = (
  items: { id: string }[] | undefined,
  listKey: string
) => {
  const [snapshot, setSnapshot] = useState<{
    items: { id: string }[]
    listKey: string
  }>()

  if (items && snapshot?.listKey !== listKey) {
    setSnapshot({ items: items.map(({ id }) => ({ id })), listKey })
  }

  return snapshot?.listKey === listKey ? snapshot.items : items
}
