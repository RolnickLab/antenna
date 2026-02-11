import { isBefore, isValid } from 'date-fns'
import { useParams, useSearchParams } from 'react-router-dom'
import { APP_ROUTES } from './constants'
import { STRING, translate } from './language'
import { SEARCH_PARAM_KEY_PAGE } from './usePagination'

interface FilterConfig {
  label: string
  field: string
  info?: {
    text: string
    to?: string
  }
  validate?: (
    value?: string,
    filters?: { field: string; value?: string }[]
  ) => string | undefined
}

export const AVAILABLE_FILTERS = (projectId: string): FilterConfig[] => [
  {
    label: 'Include algorithm',
    field: 'algorithm',
  },
  {
    label: translate(STRING.FIELD_LABEL_CAPTURE_SET),
    field: 'collection', // This is for viewing occurrences by capture set. @TODO: Can we update this key to "capture_set_id" to streamline?
    info: {
      text: translate(STRING.TOOLTIP_CAPTURE_SET),
      to: APP_ROUTES.CAPTURE_SETS({ projectId }),
    },
  },
  {
    label: translate(STRING.FIELD_LABEL_CAPTURE_SET),
    field: 'source_image_collection', // This is for viewing jobs by capture set. @TODO: Can we update this key to "capture_set_id" to streamline?
    info: {
      text: translate(STRING.TOOLTIP_CAPTURE_SET),
      to: APP_ROUTES.CAPTURE_SETS({ projectId }),
    },
  },
  {
    label: translate(STRING.FIELD_LABEL_CAPTURE_SET),
    field: 'collections', // This is for viewing captures by capture set. @TODO: Can we update this key to "capture_set_id" to streamline?
    info: {
      text: translate(STRING.TOOLTIP_CAPTURE_SET),
      to: APP_ROUTES.CAPTURE_SETS({ projectId }),
    },
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
    label: translate(STRING.FIELD_LABEL_CAPTURE),
    field: 'detections__source_image', // This is for viewing occurrences by capture. @TODO: Can we update this key to "capture_id" to streamline?
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
    label: translate(STRING.FIELD_LABEL_CAPTURE),
    field: 'source_image_single', // This is for viewing jobs by capture. @TODO: Can we update this key to "capture_id" to streamline?
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
  const { projectId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const avaibleFilters = AVAILABLE_FILTERS(projectId as string)

  const _filters = avaibleFilters.map(({ field, ...rest }) => {
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
    if (avaibleFilters.some((filter) => filter.field === field)) {
      searchParams.set(field, value)

      // Reset page param if set, when filters are updated
      if (searchParams.has(SEARCH_PARAM_KEY_PAGE)) {
        searchParams.delete(SEARCH_PARAM_KEY_PAGE)
      }

      setSearchParams(searchParams)
    }
  }

  const clearFilter = (field: string) => {
    if (avaibleFilters.some((filter) => filter.field === field)) {
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
