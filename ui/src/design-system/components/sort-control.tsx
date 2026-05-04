import classNames from 'classnames'
import { ArrowUpDownIcon } from 'lucide-react'
import { buttonVariants, Select } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { TableSortSettings } from './table/types'
import { BasicTooltip } from './tooltip/basic-tooltip'

interface SortControlProps {
  columns: { id: string; name: string; sortField?: string }[]
  setSort: (sort?: TableSortSettings) => void
  sort?: TableSortSettings
}

export const SortControl = ({ columns, setSort, sort }: SortControlProps) => {
  const column = sort
    ? columns.find((column) => column.sortField === sort.field)
    : undefined

  return (
    <Select.Root
      value={sort?.field}
      onValueChange={(value) => {
        setSort({ field: value, order: 'asc' })
      }}
    >
      <BasicTooltip asChild content={translate(STRING.SORT_BY)}>
        <Select.Trigger
          className={classNames(
            buttonVariants({ size: 'small', variant: 'outline' }),
            'w-auto'
          )}
        >
          <ArrowUpDownIcon className="w-4 h-4" />
          <span>{column ? column.name : translate(STRING.SORT_BY)}</span>
        </Select.Trigger>
      </BasicTooltip>
      <Select.Content>
        {columns
          .filter((column) => column.sortField)
          .map((column) => (
            <Select.Item key={column.id} value={column.sortField as string}>
              {column.name}
            </Select.Item>
          ))}
      </Select.Content>
    </Select.Root>
  )
}
