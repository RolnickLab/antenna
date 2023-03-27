import classNames from 'classnames'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { TableHeader } from '../table-header/table-header'
import tableHeaderStyles from '../table-header/table-header.module.scss'
import { TableColumn, TableSortSettings } from '../types'
import styles from './table.module.scss'

interface TableProps<T> {
  items: T[]
  isLoading?: boolean
  columns: TableColumn<T>[]
  sortSettings?: TableSortSettings
  onSortSettingsChange?: (sortSettings?: TableSortSettings) => void
}

export const Table = <T extends { id: string }>({
  items,
  isLoading,
  columns,
  sortSettings,
  onSortSettingsChange,
}: TableProps<T>) => {
  const onSortClick = (column: TableColumn<T>) => {
    if (column.id !== sortSettings?.columnId) {
      onSortSettingsChange?.({ columnId: column.id, orderBy: 'desc' })
    } else {
      onSortSettingsChange?.({
        columnId: column.id,
        orderBy: sortSettings.orderBy === 'asc' ? 'desc' : 'asc',
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
          items.map((item, rowIndex) => (
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
