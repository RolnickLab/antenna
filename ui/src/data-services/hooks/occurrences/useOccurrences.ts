import { API_ROUTES } from 'data-services/constants'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { Occurrence, ServerOccurrence } from '../../models/occurrence'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerOccurrence) => new Occurrence(record)

export const useOccurrences = (
  params?: FetchParams
): {
  occurrences?: Occurrence[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.OCCURRENCES, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerOccurrence[]
    count: number
  }>({
    queryKey: [API_ROUTES.OCCURRENCES, params],
    url: fetchUrl,
  })

  return {
    occurrences: data?.results.map(convertServerRecord),
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
