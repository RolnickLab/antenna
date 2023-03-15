import classNames from 'classnames'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { OrderBy, TableColumn, TableSortSettings } from '../types'
import styles from './table-header.module.scss'

interface TableHeaderProps<T> {
  column: TableColumn<T>
  sortSettings?: TableSortSettings
  onSortClick: () => void
}

export const TableHeader = <T,>({
  column,
  sortSettings,
  onSortClick,
}: TableHeaderProps<T>) => {
  if (!column.sortable) {
    return <BasicTableHeader column={column} />
  }

  return (
    <SortableTableHeader
      column={column}
      sortSettings={sortSettings}
      onSortClick={onSortClick}
    />
  )
}

const BasicTableHeader = <T,>({
  column,
}: Omit<TableHeaderProps<T>, 'sortSettings' | 'onSortClick'>) => (
  <th
    key={column.id}
    style={{ textAlign: column.textAlign }}
    className={styles.tableHeader}
  >
    <div className={styles.content}>
      <div className={styles.columnName}>
        <span>{column.name}</span>
      </div>
    </div>
  </th>
)

const SortableTableHeader = <T,>({
  column,
  sortSettings,
  onSortClick,
}: TableHeaderProps<T>) => {
  const sortActive = sortSettings?.columnId === column.id

  const ariaSort = (() => {
    if (!sortActive) {
      return undefined
    }
    return sortSettings?.orderBy === OrderBy.Ascending
      ? 'ascending'
      : 'descending'
  })()

  return (
    <th
      key={column.id}
      aria-sort={ariaSort}
      style={{ textAlign: column.textAlign }}
      className={classNames(styles.tableHeader, {
        [styles.active]: sortActive,
      })}
    >
      <button
        className={classNames(styles.content, styles.sortButton)}
        onClick={onSortClick}
      >
        <div className={styles.columnName}>
          <span>{column.name}</span>
          <div
            className={classNames(styles.iconWrapper, {
              [styles.visible]: sortActive,
              [styles.ascending]:
                sortActive && sortSettings?.orderBy === OrderBy.Ascending,
            })}
          >
            <Icon type={IconType.Sort} theme={IconTheme.Neutral} />
          </div>
        </div>
      </button>
    </th>
  )
}
