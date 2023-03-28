import { TableSortSettings } from 'design-system/components/table/types'
import _ from 'lodash'
import { useEffect, useState } from 'react'

export const useClientSideSort = <T>({
  items,
  defaultSort,
}: {
  items: T[]
  defaultSort?: TableSortSettings
}) => {
  const [sortedItems, setSortedItems] = useState(items)
  const [sort, setSort] = useState<TableSortSettings | undefined>(defaultSort)

  useEffect(() => {
    if (sort) {
      setSortedItems(_.orderBy(items, sort.field, sort.order))
    } else {
      setSortedItems(items)
    }
  }, [items, sort])

  return { sortedItems, sort, setSort }
}
