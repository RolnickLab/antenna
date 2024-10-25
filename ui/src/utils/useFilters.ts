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
    label: 'Score threshold',
    field: 'classification_threshold',
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

export const useFilters = (
  defaultFilters?: { field: string; value: string }[]
) => {
  const [searchParams, setSearchParams] = useSearchParams()

  const filters = AVAILABLE_FILTERS.map((filter) => {
    const value = searchParams.getAll(filter.field)[0]
    const defaultValue = defaultFilters?.find(
      (defaultFilter) => defaultFilter.field === filter.field
    )?.value

    return {
      ...filter,
      value: value ?? defaultValue,
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
