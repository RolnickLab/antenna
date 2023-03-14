import _ from 'lodash'
import { useEffect, useState } from 'react'
import { TableHeader } from '../table-header/table-header'
import tableHeaderStyles from '../table-header/table-header.module.scss'
import { OrderBy, TableColumn, TableSortSettings } from '../types'
import styles from './table.module.scss'

interface TableProps<T> {
  items: T[]
  columns: TableColumn<T>[]
  defaultSortSettings?: TableSortSettings
}

export const Table = <T,>({
  items,
  columns,
  defaultSortSettings,
}: TableProps<T>) => {
  const [sortedItems, setSortedItems] = useState(items)
  const [sortSettings, setSortSettings] = useState(defaultSortSettings)

  useEffect(() => {
    if (sortSettings) {
      const column = columns.find((c) => c.id === sortSettings?.columnId)
      if (column) {
        return setSortedItems(
          _.orderBy(items, column.field, sortSettings.orderBy)
        )
      }
    }

    setSortedItems(items)
  }, [sortSettings])

  const onSortClick = (column: TableColumn<T>) => {
    if (column.id !== sortSettings?.columnId) {
      setSortSettings({ columnId: column.id, orderBy: OrderBy.Descending })
    } else {
      setSortSettings({
        columnId: column.id,
        orderBy:
          sortSettings.orderBy === OrderBy.Ascending
            ? OrderBy.Descending
            : OrderBy.Ascending,
      })
    }
  }

  return (
    <table className={styles.table}>
      <thead>
        <tr>
          {columns.map((column) => (
            <TableHeader
              key={column.id}
              column={column}
              sortSettings={sortSettings}
              onSortClick={() => onSortClick(column)}
            />
          ))}
          <th
            aria-hidden="true"
            className={tableHeaderStyles.tableHeader}
            style={{ width: '100%' }}
          />
        </tr>
      </thead>
      <tbody>
        {sortedItems.map((item, index) => (
          <tr key={index}>
            {columns.map((column, index) => (
              <td key={index}>{column.renderCell(item)}</td>
            ))}
            <td aria-hidden="true" />
          </tr>
        ))}
      </tbody>
    </table>
  )
}
