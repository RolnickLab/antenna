import { API_ROUTES, API_URL } from 'data-services/constants'
import { ServerJob } from 'data-services/models/job'
import { JobDetails, ServerJobDetails } from 'data-services/models/job-details'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const REFETCH_INTERVAL = 10000 // Refetch every 10 second

const convertServerRecord = (record: ServerJob) => new JobDetails(record)

export const useJobDetails = (
  id: string
): {
  job?: JobDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<ServerJobDetails>({
      queryKey: [API_ROUTES.JOBS, id],
      url: `${API_URL}/${API_ROUTES.JOBS}/${id}/`,
      refetchInterval: REFETCH_INTERVAL,
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
