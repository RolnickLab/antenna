import _ from 'lodash'
import { useEffect, useState } from 'react'
import { TableColumn, TableSortSettings } from '../types'
import { Table } from './table'

interface SimpleTableProps<T> {
  items: T[]
  isLoading?: boolean
  columns: TableColumn<T>[]
  defaultSortSettings?: TableSortSettings
}

export const SimpleTable = <T extends { id: string }>({
  items,
  isLoading,
  columns,
  defaultSortSettings,
}: SimpleTableProps<T>) => {
  const [sortedItems, setSortedItems] = useState(items)
  const [sortSettings, setSortSettings] = useState(defaultSortSettings)

  useEffect(() => {
    if (sortSettings) {
      const column = columns.find((c) => c.id === sortSettings?.columnId)
      if (column?.sortField) {
        setSortedItems(_.orderBy(items, column.sortField, sortSettings.orderBy))
        return
      }
    }
    setSortedItems(items)
  }, [items, sortSettings])

  return (
    <Table
      items={sortedItems}
      isLoading={isLoading}
      columns={columns}
      sortSettings={sortSettings}
      onSortSettingsChange={setSortSettings}
    />
  )
}
