import { isBefore, isValid } from 'date-fns'
import { useMemo } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { APP_ROUTES } from './constants'
import { STRING, translate } from './language'
import { SEARCH_PARAM_KEY_PAGE } from './usePagination'

interface FilterConfig {
  label: string
  field: string
  tooltip?: {
    text: string
    link?: {
      text: string
      to: string
    }
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
    tooltip: {
      text: translate(STRING.TOOLTIP_ALGORITHM),
      link: {
        text: translate(STRING.NAV_ITEM_ALGORITHMS),
        to: APP_ROUTES.ALGORITHMS({ projectId }),
      },
    },
  },
  {
    label: translate(STRING.FIELD_LABEL_CAPTURE_SET),
    field: 'collection', // This is for viewing occurrences by capture set. @TODO: Can we update this key to "capture_set_id" to streamline?
    tooltip: {
      text: translate(STRING.TOOLTIP_CAPTURE_SET),
      link: {
        text: translate(STRING.NAV_ITEM_CAPTURE_SETS),
        to: APP_ROUTES.CAPTURE_SETS({ projectId }),
      },
    },
  },
  {
    label: translate(STRING.FIELD_LABEL_CAPTURE_SET),
    field: 'source_image_collection', // This is for viewing jobs by capture set. @TODO: Can we update this key to "capture_set_id" to streamline?
    tooltip: {
      text: translate(STRING.TOOLTIP_CAPTURE_SET),
      link: {
        text: translate(STRING.NAV_ITEM_CAPTURE_SETS),
        to: APP_ROUTES.CAPTURE_SETS({ projectId }),
      },
    },
  },
  {
    label: translate(STRING.FIELD_LABEL_CAPTURE_SET),
    field: 'collections', // This is for viewing captures by capture set. @TODO: Can we update this key to "capture_set_id" to streamline?
    tooltip: {
      text: translate(STRING.TOOLTIP_CAPTURE_SET),
      link: {
        text: translate(STRING.NAV_ITEM_CAPTURE_SETS),
        to: APP_ROUTES.CAPTURE_SETS({ projectId }),
      },
    },
  },
  {
    label: 'Station',
    field: 'deployment',
    tooltip: {
      text: translate(STRING.TOOLTIP_DEPLOYMENT),
      link: {
        text: translate(STRING.NAV_ITEM_DEPLOYMENTS),
        to: APP_ROUTES.DEPLOYMENTS({ projectId }),
      },
    },
  },
  {
    label: 'Device',
    field: 'deployment__device',
  },
  {
    label: 'Site',
    field: 'deployment__research_site',
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
    tooltip: {
      text: translate(STRING.TOOLTIP_CAPTURE),
      link: {
        text: translate(STRING.NAV_ITEM_CAPTURES),
        to: APP_ROUTES.CAPTURES({ projectId }),
      },
    },
  },
  {
    label: 'Session',
    field: 'event',
    tooltip: {
      text: translate(STRING.TOOLTIP_SESSION),
      link: {
        text: translate(STRING.NAV_ITEM_SESSIONS),
        to: APP_ROUTES.SESSIONS({ projectId }),
      },
    },
  },
  {
    label: 'Processing status',
    field: 'processed',
    tooltip: {
      text: 'Filter captures by whether they have been processed by a detection pipeline.',
    },
  },
  {
    label: 'Pipeline',
    field: 'pipeline',
    tooltip: {
      text: translate(STRING.TOOLTIP_PIPELINE),
      link: {
        text: translate(STRING.NAV_ITEM_PIPELINES),
        to: APP_ROUTES.PIPELINES({ projectId }),
      },
    },
  },
  {
    label: 'Exclude algorithm',
    field: 'not_algorithm',
    tooltip: {
      text: translate(STRING.TOOLTIP_ALGORITHM),
      link: {
        text: translate(STRING.NAV_ITEM_ALGORITHMS),
        to: APP_ROUTES.ALGORITHMS({ projectId }),
      },
    },
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
  const availableFilters = AVAILABLE_FILTERS(projectId as string)

  const _filters = availableFilters.map(({ field, ...rest }) => {
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
    if (availableFilters.some((filter) => filter.field === field)) {
      searchParams.set(field, value)

      // Reset page param if set, when filters are updated
      if (searchParams.has(SEARCH_PARAM_KEY_PAGE)) {
        searchParams.delete(SEARCH_PARAM_KEY_PAGE)
      }

      setSearchParams(searchParams)
    }
  }

  const clearFilter = (field: string) => {
    if (availableFilters.some((filter) => filter.field === field)) {
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

// Filter carry-over between list views, keyed by DESTINATION.
//
// Each constant is the set of filter fields the destination list understands. The source
// is implicit: when a link is followed, whichever of these fields is currently active in
// the source view is carried into the destination URL, so the destination keeps the same
// scope (station, device, site, verification, ...) instead of resetting. Listing the
// destination's own fields — rather than copying the whole query string — keeps
// source-only state (sort order, page number, or a filter the destination does not
// support) out of the URL. Any view that links to a destination reuses its set, so the
// behavior stays consistent no matter where the link is.

export const FILTERS_TO_OCCURRENCES = [
  'detections__source_image',
  'event',
  'taxon',
  'taxa_list_id',
  'not_taxa_list_id',
  'verified',
  'verified_by_me',
  'collection',
  'date_start',
  'date_end',
  'deployment',
  'deployment__device',
  'deployment__research_site',
  'algorithm',
  'not_algorithm',
  'apply_defaults',
]

export const FILTERS_TO_TAXA = [
  'event',
  'taxon',
  'taxa_list_id',
  'not_taxa_list_id',
  'verified',
  'include_unobserved',
  'deployment',
  'deployment__device',
  'deployment__research_site',
  'tag_id',
  'not_tag_id',
  'apply_defaults',
]

// Intersect the active filters with the fields the destination list understands, as a
// plain object ready to spread into a `getAppRoute({ filters })` call.
export const buildCarryOverFilters = (
  filters: { field: string; value?: string }[],
  fields: string[]
): Record<string, string> =>
  filters.reduce<Record<string, string>>((acc, filter) => {
    if (filter.value && fields.includes(filter.field)) {
      acc[filter.field] = filter.value
    }
    return acc
  }, {})

// Hook form of buildCarryOverFilters: pass the destination's field set (e.g.
// FILTERS_TO_OCCURRENCES). Reads the active filters of the current view, so any link into
// that destination — from any source view — carries a consistent set.
export const useCarryOverFilters = (
  fields: string[]
): Record<string, string> => {
  const { filters } = useFilters()
  return useMemo(
    () => buildCarryOverFilters(filters, fields),
    [filters, fields]
  )
}
