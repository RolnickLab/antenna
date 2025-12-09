type FilterType =
  | 'deployment'
  | 'event'
  | 'occurrence'
  | 'capture'
  | 'detections__source_image'
  | 'taxon'
  | 'timestamp'
  | 'collection'
  | 'collections'
  | 'source_image_collection'
  | 'source_image_single'

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
