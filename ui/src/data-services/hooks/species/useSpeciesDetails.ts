import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'

import {
  ServerSpeciesDetails,
  SpeciesDetails,
} from 'data-services/models/species-details'
import { COLLECTION } from './constants'

const convertServerRecord = (record: ServerSpeciesDetails) =>
  new SpeciesDetails(record)

export const useSpeciesDetails = (
  id: string
): {
  species?: SpeciesDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, id],
    queryFn: () =>
      axios
        .get<SpeciesDetails>(`${API_URL}/${COLLECTION}/${id}`)
        .then((res) => convertServerRecord(res.data)),
  })

  return {
    species: data,
    isLoading,
    isFetching,
    error,
  }
}
