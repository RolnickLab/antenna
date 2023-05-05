import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { Occurrence, ServerOccurrence } from '../models/occurrence'

const COLLECTION = 'occurrences'

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
  const fetchUrl = getFetchUrl({ collection: COLLECTION, params })

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, params],
    queryFn: () =>
      axios
        .get<ServerOccurrence[]>(fetchUrl)
        .then((res) => res.data.map(convertServerRecord)),
  })

  return {
    occurrences: data,
    total: data?.length ?? 0, // TODO: Until we get total in response
    isLoading,
    isFetching,
    error,
  }
}
