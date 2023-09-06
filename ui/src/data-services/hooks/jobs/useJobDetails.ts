import { API_ROUTES, API_URL } from 'data-services/constants'
import { JobDetails, ServerJobDetails } from 'data-services/models/job-details'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

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
    })

  return {
    job: data,
    isLoading,
    isFetching,
    error,
  }
}
