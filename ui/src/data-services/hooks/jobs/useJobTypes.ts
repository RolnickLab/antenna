import { API_ROUTES, API_URL } from 'data-services/constants'
import { ServerJobType } from 'data-services/models/job-type'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

export const useJobTypes = (
  projectId?: string
): {
  jobTypes?: ServerJobType[]
  isLoading: boolean
  error?: unknown
} => {
  const { data, isLoading, error } = useAuthorizedQuery<{
    results: ServerJobType[]
  }>({
    enabled: !!projectId,
    queryKey: [API_ROUTES.JOB_TYPES, projectId],
    url: `${API_URL}/${API_ROUTES.JOB_TYPES}/?project_id=${projectId}`,
  })

  return { jobTypes: data?.results, isLoading, error }
}
