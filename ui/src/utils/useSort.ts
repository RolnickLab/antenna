import { TableSortSettings } from 'nova-ui-kit'
import { useSearchParams } from 'react-router-dom'

const SEARCH_PARAM_KEY_ORDERING = 'ordering'

// `seedParams` maps a search param to the only sort field that uses it. Switching to
// any other sort removes the param, so the URL does not claim a seed that is ignored.
export const useSort = (
  defaultSort?: TableSortSettings,
  seedParams?: { [param: string]: string }
) => {
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

    Object.entries(seedParams ?? {}).forEach(([param, field]) => {
      if (sort?.field !== field) {
        searchParams.delete(param)
      }
    })

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
