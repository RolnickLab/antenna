type FilterType =
  | 'deployment'
  | 'event'
  | 'occurrence'
  | 'capture'
  | 'detections__source_image'
  | 'taxon'
  | 'timestamp'
  | 'collection'

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
    if (value !== undefined) {
      searchParams.set(name, value)
    }
  })
  if (searchParams.toString().length) {
    url = `${url}?${searchParams}`
  }

  return url
}
