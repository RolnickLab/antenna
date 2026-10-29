import { API_ROUTES, API_URL } from 'data-services/constants'
import { ServerJobGroup, ServerJobType } from 'data-services/models/job-type'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

export const useJobTypes = (
  projectId?: string
): {
  jobTypes?: ServerJobType[]
  groups?: ServerJobGroup[]
  isLoading: boolean
  error?: unknown
} => {
  const { data, isLoading, error } = useAuthorizedQuery<{
    groups: ServerJobGroup[]
    results: ServerJobType[]
  }>({
    enabled: !!projectId,
    queryKey: [API_ROUTES.JOB_TYPES, projectId],
    url: `${API_URL}/${API_ROUTES.JOB_TYPES}/?project_id=${projectId}`,
  })

  return { jobTypes: data?.results, groups: data?.groups, isLoading, error }
}
