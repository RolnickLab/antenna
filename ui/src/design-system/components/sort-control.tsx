import classNames from 'classnames'
import { ArrowDownIcon, ArrowUpDownIcon } from 'lucide-react'
import { Button, buttonVariants, Select } from 'nova-ui-kit'
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

  const changeSortField = (field: string) => {
    if (sort) {
      setSort({ field, order: sort.order })
    } else {
      setSort({ field, order: 'asc' })
    }
  }

  const changeSortOrder = () => {
    if (sort) {
      setSort({
        field: sort.field,
        order: sort.order === 'asc' ? 'desc' : 'asc',
      })
    }
  }

  return (
    <div className="flex items-center gap-1">
      <Select.Root value={sort?.field} onValueChange={changeSortField}>
        <BasicTooltip asChild content={translate(STRING.SORT_BY)}>
          <Select.Trigger
            className={classNames(
              buttonVariants({ size: 'small', variant: 'outline' }),
              'w-auto'
            )}
            hideIcon={!!sort}
          >
            <span>{column ? column.name : translate(STRING.SORT_BY)}</span>
            {sort ? (
              <ArrowDownIcon
                className={classNames(
                  'w-4 h-4 transition-transform duration-300',
                  {
                    '-rotate-180': sort.order !== 'asc',
                    'rotate-0': sort.order === 'asc',
                  }
                )}
              />
            ) : null}
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
      {sort ? (
        <BasicTooltip asChild content={translate(STRING.CHANGE_SORT_ORDER)}>
          <Button onClick={changeSortOrder} size="icon" variant="ghost">
            <ArrowUpDownIcon
              className={classNames(
                'w-4 h-4 transition-transform duration-300',
                {
                  '-rotate-180': sort.order !== 'asc',
                  'rotate-0': sort.order === 'asc',
                }
              )}
            />
          </Button>
        </BasicTooltip>
      ) : null}
    </div>
  )
}
