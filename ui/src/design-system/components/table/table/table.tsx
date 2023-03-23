import classNames from 'classnames'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import _ from 'lodash'
import { useEffect, useState } from 'react'
import { TableHeader } from '../table-header/table-header'
import tableHeaderStyles from '../table-header/table-header.module.scss'
import { OrderBy, TableColumn, TableSortSettings } from '../types'
import styles from './table.module.scss'

interface TableProps<T> {
  items: T[]
  isLoading?: boolean
  columns: TableColumn<T>[]
  defaultSortSettings?: TableSortSettings
}

export const Table = <T extends { id: string }>({
  items,
  isLoading,
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
  }, [items, sortSettings])

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
              visuallyHidden={column.visuallyHidden}
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
      <tbody className={classNames({ [styles.loading]: isLoading })}>
        {isLoading ? (
          <tr>
            <td colSpan={columns.length + 1}>
              <LoadingSpinner />
            </td>
          </tr>
        ) : (
          sortedItems.map((item, rowIndex) => (
            <tr key={item.id}>
              {columns.map((column, columnIndex) => (
                <td key={column.id}>
                  {column.renderCell(item, rowIndex, columnIndex)}
                </td>
              ))}
              <td aria-hidden="true" />
            </tr>
          ))
        )}
      </tbody>
    </table>
  )
}
