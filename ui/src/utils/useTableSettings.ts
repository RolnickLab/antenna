import { FetchParams } from 'data-services/types'
import {
  TablePaginationSettings,
  TableSortSettings,
} from 'design-system/components/table/types'
import { useMemo, useState } from 'react'

export const useTableSettings = ({
  columns,
  defaultSort,
  defaultPagination = { page: 0, perPage: 5 },
}: {
  columns: { id: string; sortField?: string }[]
  defaultSort?: TableSortSettings
  defaultPagination?: TablePaginationSettings
}) => {
  const [sort, setSort] = useState<TableSortSettings | undefined>(defaultSort)
  const [pagination, setPagination] =
    useState<TablePaginationSettings>(defaultPagination)
  const fetchParams = useMemo<FetchParams>(
    () => ({
      sort: parseSortSettings({ sort, columns }),
      pagination,
    }),
    [sort, pagination, columns]
  )

  return {
    sort,
    setSort,
    pagination,
    setPagination,
    fetchParams,
  }
}

const parseSortSettings = ({
  columns,
  sort,
}: {
  columns: { id: string; sortField?: string }[]
  sort?: TableSortSettings
}) => {
  if (!sort) {
    return undefined
  }

  const column = columns.find((c) => c.id === sort?.columnId)
  if (!column?.sortField) {
    return undefined
  }

  return {
    field: column.sortField,
    order: sort.order,
  }
}
