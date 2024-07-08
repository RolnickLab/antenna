import { useSearchParams } from 'react-router-dom'

const AVAILABLE_FILTERS = [
  {
    label: 'Deployment',
    field: 'deployment',
  },
  {
    label: 'Occurrence deployment',
    field: 'occurrences__deployment',
  },
  {
    label: 'Session',
    field: 'event',
  },
  {
    label: 'Occurrence session',
    field: 'occurrences__event',
  },
  {
    label: 'Species',
    field: 'determination',
  },
]

export const useFilters = () => {
  const [searchParams, setSearchParams] = useSearchParams()

  const filters = AVAILABLE_FILTERS.map((filter) => {
    const values = searchParams.getAll(filter.field)

    return {
      ...filter,
      value: values[0],
    }
  })

  const isActive = filters.some((filter) => filter.value?.length)

  const clearFilter = (field: string) => {
    AVAILABLE_FILTERS.filter((filter) => filter.field === field).forEach(
      (filter) => {
        searchParams.delete(filter.field)
      }
    )
    setSearchParams(searchParams)
  }

  return {
    filters,
    isActive,
    clearFilter,
  }
}
