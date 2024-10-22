import { useSearchParams } from 'react-router-dom'

const AVAILABLE_FILTERS = [
  {
    label: 'Station',
    field: 'deployment',
  },
  {
    label: 'Occurrence station',
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
    label: 'Taxon',
    field: 'taxon',
  },
  {
    label: 'Capture collection',
    field: 'collection',
  },
  {
    label: 'Capture',
    field: 'detections__source_image',
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

  const addFilter = (field: string, value: string) => {
    if (AVAILABLE_FILTERS.some((filter) => filter.field === field)) {
      searchParams.set(field, value)
      setSearchParams(searchParams)
    }
  }

  const clearFilter = (field: string) => {
    if (AVAILABLE_FILTERS.some((filter) => filter.field === field)) {
      searchParams.delete(field)
      setSearchParams(searchParams)
    }
  }

  return {
    filters,
    isActive,
    addFilter,
    clearFilter,
  }
}
