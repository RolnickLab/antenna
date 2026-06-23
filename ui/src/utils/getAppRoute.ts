type FilterType =
  | 'apply_defaults'
  | 'capture'
  | 'collection'
  | 'collections'
  | 'date_end'
  | 'date_start'
  | 'deployment'
  | 'deployment__device'
  | 'deployment__research_site'
  | 'detections__source_image'
  | 'event'
  | 'include_unobserved'
  | 'not_taxa_list_id'
  | 'occurrence'
  | 'source_image_collection'
  | 'source_image_single'
  | 'taxa_list_id'
  | 'taxon'
  | 'timestamp'
  | 'verified'

export const getAppRoute = ({
  to,
  filters = {},
  keepSearchParams,
}: {
  to: string
  filters?: Partial<Record<FilterType, string | undefined>>
  keepSearchParams?: boolean
}) => {
  let url = `${to}`

  const searchParams = new URLSearchParams(
    keepSearchParams ? window.location.search : undefined
  )
  Object.entries(filters).forEach(([name, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.set(name, value)
    }
  })
  if (searchParams.toString().length) {
    url = `${url}?${searchParams}`
  }

  return url
}
