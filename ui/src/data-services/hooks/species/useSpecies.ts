import { API_ROUTES } from 'data-services/constants'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
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
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.SPECIES, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerSpecies[]
    count: number
  }>({
    queryKey: [API_ROUTES.SPECIES, params],
    url: fetchUrl,
  })

  return {
    species: data?.results.map(convertServerRecord),
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
