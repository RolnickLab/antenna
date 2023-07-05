import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import {
  OccurrenceDetails,
  ServerOccurrenceDetails,
} from 'data-services/models/occurrence-details'

const COLLECTION = 'occurrences'

const convertServerRecord = (record: ServerOccurrenceDetails) =>
  new OccurrenceDetails(record)

export const useOccurrenceDetails = (
  id: string
): {
  occurrence?: OccurrenceDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, id],
    queryFn: () =>
      axios
        .get<ServerOccurrenceDetails>(`${API_URL}/${COLLECTION}/${id}`)
        .then((res) => convertServerRecord(res.data)),
  })

  return {
    occurrence: data,
    isLoading,
    isFetching,
    error,
  }
}
