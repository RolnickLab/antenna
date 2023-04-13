import { TablePaginationSettings } from 'design-system/components/table/types'
import { useCallback, useState } from 'react'

export const usePagination = ({
  defaultPagination = { page: 0, perPage: 100 },
}: {
  defaultPagination?: TablePaginationSettings
} = {}) => {
  const [pagination, setPagination] =
    useState<TablePaginationSettings>(defaultPagination)

  const setPrevPage = useCallback(
    () =>
      setPagination({
        ...pagination,
        page: pagination.page - 1,
      }),
    [pagination, setPagination]
  )

  const setNextPage = useCallback(
    () =>
      setPagination({
        ...pagination,
        page: pagination.page + 1,
      }),
    [pagination, setPagination]
  )

  return {
    pagination,
    setPrevPage,
    setNextPage,
  }
}
