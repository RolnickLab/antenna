import { isBefore, isValid } from 'date-fns'
import { useSearchParams } from 'react-router-dom'

export const AVAILABLE_FILTERS: {
  label: string
  field: string
  validate?: (
    value?: string,
    filters?: { field: string; value?: string }[]
  ) => string | undefined
}[] = [
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
    field: 'collection', // This is for viewing Occurrences by collection
  },
  {
    label: 'Collection',
    field: 'source_image_collection', // This is for viewing Jobs by collection. @TODO: Can we update this key to "collection" to streamline?
  },
  {
    label: 'Station',
    field: 'deployment',
  },
  {
    label: 'End date',
    field: 'date_end',
    validate: (value) => {
      if (!value) {
        return undefined
      }

      if (!isValid(new Date(value))) {
        return 'Date is not valid'
      }

      return undefined
    },
  },
  {
    label: 'Start date',
    field: 'date_start',
    validate: (value, filters) => {
      if (!value) {
        return undefined
      }

      if (!isValid(new Date(value))) {
        return 'Date is not valid'
      }

      const dateEnd = filters?.find(
        (filter) => filter.field === 'date_end'
      )?.value

      if (dateEnd && !isBefore(new Date(value), new Date(dateEnd))) {
        return 'Start date must be before end date'
      }

      return undefined
    },
  },
  {
    label: 'Source image',
    field: 'detections__source_image', // This is for viewing Occurrences by source image. @TODO: Can we update this key to "source_image" to streamline?
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
    field: 'source_image_single', // This is for viewing Jobs by source image. @TODO: Can we update this key to "source_image" to streamline?
  },
  {
    label: 'Status',
    field: 'status',
  },
  {
    label: 'Type',
    field: 'job_type_key',
  },
  {
    label: 'Verification status',
    field: 'verified',
  },
  {
    label: 'Verified by',
    field: 'verified_by_me',
  },
]

export const useFilters = (defaultFilters?: { [field: string]: string }) => {
  const [searchParams, setSearchParams] = useSearchParams()

  const _filters = AVAILABLE_FILTERS.map(({ field, ...rest }) => {
    const value = searchParams.get(field) ?? defaultFilters?.[field]

    return {
      ...rest,
      field,
      value,
    }
  })

  const filters = _filters.map(({ validate, value, ...rest }) => {
    const error = validate ? validate(value, _filters) : undefined
    const isValid = !error

    return {
      ...rest,
      value,
      isValid,
      error,
    }
  })

  const activeFilters = filters.filter((filter) => !!filter.value?.length)

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
    activeFilters,
    addFilter,
    clearFilter,
    filters,
  }
}
