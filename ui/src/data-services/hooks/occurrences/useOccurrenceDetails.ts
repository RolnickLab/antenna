import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  OccurrenceDetails,
  ServerOccurrenceDetails,
} from 'data-services/models/occurrence-details'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

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
  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<ServerOccurrenceDetails>({
      queryKey: [API_ROUTES.OCCURRENCES, id],
      url: `${API_URL}/${API_ROUTES.OCCURRENCES}/${id}`,
    })

  return {
    occurrence: data ? convertServerRecord(data) : undefined,
    isLoading,
    isFetching,
    error,
  }
}
