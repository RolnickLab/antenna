import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  ClassificationDetails,
  ServerClassificationDetails,
} from 'data-services/models/classification-details'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerClassificationDetails) =>
  new ClassificationDetails(record)

export const useClassificationDetails = (
  id: string,
  enabled?: boolean
): {
  classification?: ClassificationDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<ServerClassificationDetails>({
      enabled,
      queryKey: [API_ROUTES.CLASSIFICATIONS, id],
      url: `${API_URL}/${API_ROUTES.CLASSIFICATIONS}/${id}/`,
      retry: 0,
    })

  const classification = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    classification,
    isLoading,
    isFetching,
    error,
  }
}
