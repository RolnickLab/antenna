import classNames from 'classnames'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { InfoIcon } from 'lucide-react'
import { TableColumn, TableSortSettings } from '../types'
import styles from './table-header.module.scss'

interface TableHeaderProps<T> {
  column: TableColumn<T>
  sortable?: boolean
  sortSettings?: TableSortSettings
  visuallyHidden?: boolean
  onSortClick: () => void
}

export const TableHeader = <T,>({
  column,
  sortable,
  sortSettings,
  visuallyHidden,
  onSortClick,
}: TableHeaderProps<T>) => {
  if (!sortable || !column.sortField) {
    return <BasicTableHeader column={column} visuallyHidden={visuallyHidden} />
  }

  return (
    <SortableTableHeader
      column={column}
      sortSettings={sortSettings}
      visuallyHidden={visuallyHidden}
      onSortClick={onSortClick}
    />
  )
}

const BasicTableHeader = <T,>({
  column,
  visuallyHidden,
}: Omit<TableHeaderProps<T>, 'sortSettings' | 'onSortClick'>) => (
  <th
    key={column.id}
    style={{
      textAlign: column.styles?.textAlign,
      width: column.styles?.width,
    }}
    className={styles.tableHeader}
  >
    <BasicTooltip asChild content={column.tooltip}>
      <div
        className={classNames(styles.content, {
          [styles.visuallyHidden]: visuallyHidden,
        })}
        style={{ padding: column.styles?.padding }}
      >
        <div className={styles.columnName}>
          <span>{column.name}</span>
          {column.tooltip ? (
            <div className={styles.iconWrapper}>
              <InfoIcon className="w-4 h-4 text-muted-foreground" />
            </div>
          ) : null}
        </div>
      </div>
    </BasicTooltip>
  </th>
)

const SortableTableHeader = <T,>({
  column,
  sortSettings,
  visuallyHidden,
  onSortClick,
}: TableHeaderProps<T>) => {
  const sortActive = sortSettings?.field === column.sortField

  const ariaSort = (() => {
    if (!sortActive) {
      return undefined
    }
    return sortSettings?.order === 'asc' ? 'ascending' : 'descending'
  })()

  return (
    <th
      key={column.id}
      aria-sort={ariaSort}
      style={{ textAlign: column.styles?.textAlign }}
      className={classNames(styles.tableHeader, {
        [styles.active]: sortActive,
      })}
    >
      <BasicTooltip asChild content={column.tooltip}>
        <button
          className={classNames(styles.content, styles.sortButton, {
            [styles.visuallyHidden]: visuallyHidden,
          })}
          style={{ padding: column.styles?.padding }}
          onClick={onSortClick}
        >
          <div className={styles.columnName}>
            <span>{column.name}</span>
            {column.tooltip && !sortActive ? (
              <div className={styles.iconWrapper}>
                <InfoIcon className="w-4 h-4 text-muted-foreground" />
              </div>
            ) : null}
            {sortActive ? (
              <div
                className={classNames(styles.iconWrapper, {
                  [styles.ascending]:
                    sortActive && sortSettings?.order === 'asc',
                })}
              >
                <Icon type={IconType.Sort} theme={IconTheme.Neutral} />
              </div>
            ) : null}
          </div>
        </button>
      </BasicTooltip>
    </th>
  )
}
