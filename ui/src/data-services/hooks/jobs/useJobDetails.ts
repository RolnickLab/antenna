import { API_ROUTES, API_URL, REFETCH_INTERVAL } from 'data-services/constants'
import { ServerJob } from 'data-services/models/job'
import { JobDetails, ServerJobDetails } from 'data-services/models/job-details'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerJob) => new JobDetails(record)

export const useJobDetails = (
  id: string,
  enabled?: boolean
): {
  job?: JobDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<ServerJobDetails>({
      enabled,
      queryKey: [API_ROUTES.JOBS, id],
      refetchInterval: REFETCH_INTERVAL,
      url: `${API_URL}/${API_ROUTES.JOBS}/${id}/`,
    })

  const job = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    job,
    isLoading,
    isFetching,
    error,
  }
}
