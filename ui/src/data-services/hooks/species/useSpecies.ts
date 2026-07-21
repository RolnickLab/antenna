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
  // Request the example-occurrence annotations so the taxa list can show the Example
  // column and link the Last-seen / Best-score cells to a single occurrence — except
  // when a capture-set (collection) filter is active. On the ?collection= path those
  // subqueries join detections and degrade to per-row scans, which is exactly why the
  // backend gates them behind this opt-in flag, so we leave it off there.
  const hasCollectionFilter = params?.filters?.some(
    (filter) => filter.field === 'collection' && filter.value
  )
  const fetchParams = {
    ...params,
    withExampleOccurrences: !hasCollectionFilter,
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
