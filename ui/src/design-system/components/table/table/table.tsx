import classNames from 'classnames'
import { EmptyState } from 'components/empty-state/empty-state'
import { ErrorState } from 'components/error-state/error-state'
import { Checkbox } from 'design-system/components/checkbox/checkbox'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { useRef } from 'react'
import { BasicTableCell } from '../basic-table-cell/basic-table-cell'
import { TableHeader } from '../table-header/table-header'
import tableHeaderStyles from '../table-header/table-header.module.scss'
import { TableColumn, TableSortSettings } from '../types'
import { StickyHeaderTable } from './sticky-header-table'
import styles from './table.module.scss'
import { useScrollFader } from './useScrollFader'

export enum TableBackgroundTheme {
  Neutral = 'neutral',
  White = 'white',
}

interface TableProps<T> {
  backgroundTheme?: TableBackgroundTheme
  columns: TableColumn<T>[]
  error?: any
  isLoading?: boolean
  items?: T[]
  onSelectedItemsChange?: (selectedItems: string[]) => void
  onSortSettingsChange?: (sortSettings?: TableSortSettings) => void
  selectable?: boolean
  selectedItems?: string[]
  sortable?: boolean
  sortSettings?: TableSortSettings
}

export const Table = <T extends { id: string }>({
  backgroundTheme = TableBackgroundTheme.Neutral,
  columns,
  error,
  isLoading,
  items = [],
  onSelectedItemsChange,
  onSortSettingsChange,
  selectable,
  selectedItems = [],
  sortable,
  sortSettings,
}: TableProps<T>) => {
  const tableContainerRef = useRef<HTMLDivElement>(null)
  const showScrollFader = useScrollFader(tableContainerRef, [
    items,
    columns,
    tableContainerRef.current,
  ])

  if (isLoading) {
    return (
      <div className={styles.loadingWrapper}>
        <LoadingSpinner />
      </div>
    )
  }

  if (error) {
    return <ErrorState error={error} />
  }

  if (items.length === 0) {
    return <EmptyState />
  }

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
    <div
      className={classNames(styles.wrapper, {
        [styles.white]: backgroundTheme === TableBackgroundTheme.White,
      })}
    >
      <StickyHeaderTable tableContainerRef={tableContainerRef}>
        <thead>
          <tr>
            {selectable && (
              <th className={tableHeaderStyles.tableHeader}>
                <div className={tableHeaderStyles.content}>
                  <MultiSelectCheckbox
                    items={items}
                    selectedItems={selectedItems}
                    onSelectedItemsChange={onSelectedItemsChange}
                  />
                </div>
              </th>
            )}
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
        <tbody>
          {items.map((item, rowIndex) => (
            <tr key={item.id}>
              {selectable && (
                <td>
                  <BasicTableCell>
                    <Checkbox
                      checked={selectedItems.includes(item.id)}
                      onCheckedChange={(checked) => {
                        onSelectedItemsChange?.(
                          checked
                            ? [...selectedItems, item.id]
                            : selectedItems.filter((id) => id !== item.id)
                        )
                      }}
                    />
                  </BasicTableCell>
                </td>
              )}
              {columns.map((column, columnIndex) => (
                <td key={column.id}>
                  {column.renderCell(item, rowIndex, columnIndex)}
                </td>
              ))}
              <td aria-hidden="true" />
            </tr>
          ))}
        </tbody>
      </StickyHeaderTable>
      <div
        className={classNames(
          styles.overflowFader,
          {
            [styles.visible]: showScrollFader,
          },
          'no-print'
        )}
      />
    </div>
  )
}

interface MultiSelectCheckboxProps<T> {
  items: T[]
  selectedItems?: string[]
  onSelectedItemsChange?: (selectedItems: string[]) => void
}

const MultiSelectCheckbox = <T extends { id: string }>({
  items = [],
  selectedItems,
  onSelectedItemsChange,
}: MultiSelectCheckboxProps<T>) => {
  const deselectAll = () => onSelectedItemsChange?.([])
  const selectAll = () => onSelectedItemsChange?.(items.map((item) => item.id))

  const checked = (() => {
    if (!selectedItems?.length) {
      return false
    }
    if (selectedItems?.length === items.length) {
      return true
    }
    return 'indeterminate'
  })()

  return (
    <BasicTooltip
      asChild
      content={checked === true ? 'Deselect all' : 'Select all'}
    >
      <div>
        <Checkbox
          checked={checked}
          onCheckedChange={(checked) => {
            if (checked) {
              selectAll()
            } else {
              deselectAll()
            }
          }}
        />
      </div>
    </BasicTooltip>
  )
}
