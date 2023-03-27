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
  sortable?: boolean
  sortSettings?: TableSortSettings
  onSortSettingsChange?: (sortSettings?: TableSortSettings) => void
}

export const Table = <T extends { id: string }>({
  items,
  isLoading,
  columns,
  sortable,
  sortSettings,
  onSortSettingsChange,
}: TableProps<T>) => {
  const onSortClick = (column: TableColumn<T>) => {
    if (!column.sortField) {
      return
    }

    if (column.sortField !== sortSettings?.field) {
      onSortSettingsChange?.({ field: column.sortField, order: 'desc' })
    } else {
      onSortSettingsChange?.({
        field: column.sortField,
        order: sortSettings.order === 'asc' ? 'desc' : 'asc',
      })
    }
  }

  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            {columns.map((column) => (
              <TableHeader
                key={column.id}
                column={column}
                sortable={sortable}
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
          {items.map((item, rowIndex) => (
            <tr key={item.id}>
              {columns.map((column, columnIndex) => (
                <td key={column.id}>
                  {column.renderCell(item, rowIndex, columnIndex)}
                </td>
              ))}
              <td aria-hidden="true" />
            </tr>
          ))}
        </tbody>
      </table>
      {isLoading && (
        <div className={styles.loadingWrapper}>
          <LoadingSpinner />
        </div>
      )}
    </div>
  )
}
