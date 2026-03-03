type FilterType =
  | 'capture'
  | 'collection'
  | 'collections'
  | 'deployment'
  | 'detections__source_image'
  | 'event'
  | 'include_unobserved'
  | 'occurrence'
  | 'source_image_collection'
  | 'source_image_single'
  | 'taxa_list_id'
  | 'taxon'
  | 'timestamp'

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
