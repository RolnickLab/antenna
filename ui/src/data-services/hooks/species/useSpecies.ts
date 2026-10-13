import { API_ROUTES } from 'data-services/constants'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { ServerSpecies, Species } from '../../models/species'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerSpecies) => new Species(record)

export const useSpecies = (
  params?: FetchParams
): {
  species?: Species[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  // Only the caller that renders the Example column asks for example occurrences, and
  // never under a capture-set (collection) filter: on that path the example subqueries
  // degrade to per-row scans, which is why the backend keeps them opt-in.
  const hasCollectionFilter = params?.filters?.some(
    (filter) => filter.field === 'collection' && filter.value
  )
  const fetchParams = {
    ...params,
    withExampleOccurrences:
      !!params?.withExampleOccurrences && !hasCollectionFilter,
  }
  const fetchUrl = getFetchUrl({
    collection: API_ROUTES.SPECIES,
    params: fetchParams,
  })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerSpecies[]
    count: number
  }>({
    queryKey: [API_ROUTES.SPECIES, params],
    url: fetchUrl,
  })

  const species = useMemo(() => data?.results.map(convertServerRecord), [data])

  return {
    species,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
