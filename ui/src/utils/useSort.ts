import { TableSortSettings } from 'design-system/components/table/types'
import { useSearchParams } from 'react-router-dom'

const SEARCH_PARAM_KEY_ORDERING = 'ordering'

export const useSort = (defaultSort?: TableSortSettings) => {
  const [searchParams, setSearchParams] = useSearchParams()
  const ordering = searchParams.get(SEARCH_PARAM_KEY_ORDERING)

  const sort: TableSortSettings | undefined = (() => {
    if (!ordering) {
      return undefined
    }

    return {
      field: ordering.replace('-', ''),
      order: ordering.includes('-') ? 'desc' : 'asc',
    }
  })()

  const setSort = (sort: TableSortSettings | undefined) => {
    searchParams.delete(SEARCH_PARAM_KEY_ORDERING)

    if (sort) {
      const newOrdering = `${sort.order === 'desc' ? '-' : ''}${sort.field}`
      searchParams.set(SEARCH_PARAM_KEY_ORDERING, newOrdering)
    }

    setSearchParams(searchParams)
  }

  return {
    sort: sort ?? defaultSort,
    setSort,
  }
}
