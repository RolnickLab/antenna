import { API_ROUTES, API_URL } from 'data-services/constants'
import { ServerJob } from 'data-services/models/job'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

/**
 * Load the name of one job for a job picker, without the polling the job details page uses.
 */
export const useJobChoice = (jobId?: string, enabled = true) => {
  const { data, isLoading } = useAuthorizedQuery<ServerJob>({
    enabled: enabled && !!jobId,
    queryKey: [API_ROUTES.JOBS, jobId, 'choice'],
    url: `${API_URL}/${API_ROUTES.JOBS}/${jobId}/?logs_limit=1`,
  })

  return {
    job: data ? { id: `${data.id}`, name: data.name } : undefined,
    isLoading,
  }
}
