import { API_ROUTES, REFETCH_INTERVAL } from 'data-services/constants'
import {
  CaptureDetails,
  ServerCaptureDetails,
} from 'data-services/models/capture-details'
import { getFetchDetailsUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerCaptureDetails) =>
  new CaptureDetails(record)

export const useCaptureDetails = ({
  id,
  poll,
  projectId,
}: {
  id: string
  poll?: boolean
  projectId: string
}): {
  capture?: CaptureDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const url = useMemo(() => {
    if (!id) return ''

    return getFetchDetailsUrl({
      collection: API_ROUTES.CAPTURES,
      itemId: id,
      projectId,
    })
  }, [id, projectId])

  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<CaptureDetails>({
      enabled: !!id,
      queryKey: [API_ROUTES.CAPTURES, id, projectId],
      refetchInterval: poll ? REFETCH_INTERVAL : undefined,
      url,
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
