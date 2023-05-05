import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { ServerOccurrence } from '../models/occurrence'
import { ServerSpecies, Species } from '../models/species'

const COLLECTION = 'species'

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
  const fetchUrl = getFetchUrl({ collection: COLLECTION, params })

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, params],
    queryFn: () =>
      axios
        .get<ServerOccurrence[]>(fetchUrl)
        .then((res) => res.data.map(convertServerRecord)),
  })

  return {
    species: data,
    total: data?.length ?? 0, // TODO: Until we get total in response
    isLoading,
    isFetching,
    error,
  }
}
