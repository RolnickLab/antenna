import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  OccurrenceDetails,
  ServerOccurrenceDetails,
} from 'data-services/models/occurrence-details'
import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
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
  // Carried through from the URL so a link to an occurrence a track edit just created
  // opens it. Such an occurrence can score under the project's default threshold, which
  // hides machine guesses but should not hide a record a person deliberately made.
  const [searchParams] = useSearchParams()
  const applyDefaults = searchParams.get('apply_defaults')
  const url =
    applyDefaults === 'false'
      ? `${API_URL}/${API_ROUTES.OCCURRENCES}/${id}/?apply_defaults=false`
      : `${API_URL}/${API_ROUTES.OCCURRENCES}/${id}/`

  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<ServerOccurrenceDetails>({
      queryKey: [API_ROUTES.OCCURRENCES, id, applyDefaults],
      url,
    })

  const occurrence = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    occurrence,
    isLoading,
    isFetching,
    error,
  }
}
