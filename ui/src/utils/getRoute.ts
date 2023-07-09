type CollectionType =
  | 'jobs'
  | 'deployments'
  | 'sessions'
  | 'occurrences'
  | 'species'

type FilterType =
  | 'deployment'
  | 'event'
  | 'determination'
  | 'occurrences__deployment'
  | 'occurrences__event'
  | 'occurrence'
  | 'capture'

export const getRoute = ({
  collection,
  itemId,
  filters = {},
  keepSearchParams,
}: {
  collection: CollectionType
  itemId?: string
  filters?: Partial<Record<FilterType, string | undefined>>
  keepSearchParams?: boolean
}) => {
  let url = `/${collection}`

  if (itemId?.length) {
    url = `${url}/${itemId}`
  }

  const searchParams = new URLSearchParams(
    keepSearchParams ? window.location.search : undefined
  )
  Object.entries(filters).forEach(([name, value]) => {
    if (value !== undefined) {
      searchParams.set(name, value)
    }
  })

  const queryString = searchParams.toString()
  if (queryString.length) {
    url = `${url}?${queryString}`
  }

  return url
}
