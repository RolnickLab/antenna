import { isBefore, isValid } from 'date-fns'
import { useSearchParams } from 'react-router-dom'
import { SEARCH_PARAM_KEY_PAGE } from './usePagination'

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
    label: 'Collection',
    field: 'collection', // This is for viewing Occurrences by collection
  },
  {
    label: 'Collection',
    field: 'source_image_collection', // This is for viewing Jobs by collection. @TODO: Can we update this key to "collection" to streamline?
  },
  {
    label: 'Collection',
    field: 'collections', // This is for viewing Captures by collection @TODO: Can we update this key to "collection" to streamline?
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
    label: 'Include tag',
    field: 'tag_id',
  },
  {
    label: 'Exclude tag',
    field: 'not_tag_id',
  },
  {
    label: 'Taxon',
    field: 'taxon',
  },
  {
    label: 'Include taxa in list',
    field: 'taxa_list_id',
  },
  {
    label: 'Exclude taxa from list',
    field: 'not_taxa_list_id',
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
  {
    label: 'Show unobserved taxa',
    field: 'include_unobserved',
  },
  {
    label: 'Default filters',
    field: 'apply_defaults',
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

    return {
      ...rest,
      value,
      error,
    }
  })

  const activeFilters = filters.filter((filter) => !!filter.value?.length)

  const addFilter = (field: string, value: string) => {
    if (AVAILABLE_FILTERS.some((filter) => filter.field === field)) {
      searchParams.set(field, value)

      // Reset page param if set, when filters are updated
      if (searchParams.has(SEARCH_PARAM_KEY_PAGE)) {
        searchParams.delete(SEARCH_PARAM_KEY_PAGE)
      }

      setSearchParams(searchParams)
    }
  }

  const clearFilter = (field: string) => {
    if (AVAILABLE_FILTERS.some((filter) => filter.field === field)) {
      searchParams.delete(field)

      // Reset page param if set, when filters are updated
      if (searchParams.has(SEARCH_PARAM_KEY_PAGE)) {
        searchParams.delete(SEARCH_PARAM_KEY_PAGE)
      }

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
