import { API_ROUTES, API_URL } from 'data-services/constants'
import { ChartsSection } from 'data-services/models/charts'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

export const useProjectCharts = (
  projectId: string
): {
  projectCharts?: ChartsSection[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    summary_data: ChartsSection[]
  }>({
    queryKey: [API_ROUTES.PROJECTS, projectId, 'charts'],
    url: `${API_URL}/${API_ROUTES.PROJECTS}/${projectId}/charts`,
  })

  return {
    projectCharts: data?.summary_data,
    isLoading,
    isFetching,
    error,
  }
}
