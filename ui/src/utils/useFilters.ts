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
    field: 'source_image_collection', // TODO: Can we update this key to "collection" to streamline?
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
    label: 'Image',
    field: 'detections__source_image', // TODO: Can we update this key to "source_image" to streamline?
  },
  {
    label: 'Session',
    field: 'event',
  },
  {
    label: 'Pipeline',
    field: 'pipeline',
  },
  {
    label: 'Exclude algorithm',
    field: 'not_algorithm',
  },
  {
    label: 'Taxon',
    field: 'taxon',
  },
  {
    label: 'Source image',
    field: 'source_image_single', // TODO: Can we update this key to "source_image" to streamline?
  },
  {
    label: 'Source image collection',
    field: 'source_image_collection',
  },
  {
    label: 'Status',
    field: 'status',
  },
  {
    label: 'Type',
    field: 'type',
  },
  {
    label: 'Verification status',
    field: 'verified',
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
