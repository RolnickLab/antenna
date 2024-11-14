import { useSearchParams } from 'react-router-dom'

export const AVAILABLE_FILTERS = [
  {
    label: 'Include algorithm',
    field: 'algorithm',
  },
  {
    label: 'Score threshold',
    field: 'classification_threshold',
  },
  {
    label: 'Collection',
    field: 'collection',
  },
  {
    label: 'Station',
    field: 'deployment',
  },
  {
    label: 'End date',
    field: 'date_end',
  },
  {
    label: 'Start date',
    field: 'date_start',
  },
  {
    label: 'Station',
    field: 'deployment',
  },
  {
    label: 'Image',
    field: 'detections__source_image',
  },
  {
    label: 'Session',
    field: 'event',
  },
  {
    label: 'Verification status',
    field: 'verified',
  },
  {
    label: 'Exclude algorithm',
    field: 'not_algorithm',
  },
]

export const useFilters = (defaultFilters?: { [field: string]: string }) => {
  const [searchParams, setSearchParams] = useSearchParams()

  const filters = AVAILABLE_FILTERS.map((filter) => {
    const value = searchParams.getAll(filter.field)[0]

    return {
      ...filter,
      value: value ?? defaultFilters?.[filter.field],
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
