import { API_ROUTES, API_URL, REFETCH_INTERVAL } from 'data-services/constants'
import {
  CaptureDetails,
  ServerCaptureDetails,
} from 'data-services/models/capture-details'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerCaptureDetails) =>
  new CaptureDetails(record)

export const useCaptureDetails = (
  id?: string,
  poll?: boolean
): {
  capture?: CaptureDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<CaptureDetails>({
      enabled: !!id,
      queryKey: [API_ROUTES.CAPTURES, id],
      refetchInterval: poll ? REFETCH_INTERVAL : undefined,
      url: `${API_URL}/${API_ROUTES.CAPTURES}/${id}/`,
    })

  const capture = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    capture,
    isLoading,
    isFetching,
    error,
  }
}
