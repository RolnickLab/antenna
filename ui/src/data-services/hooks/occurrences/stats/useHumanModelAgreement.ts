import { API_ROUTES, API_URL } from 'data-services/constants'
import { useAuthorizedQuery } from '../../auth/useAuthorizedQuery'

interface Response {
  project_id: number
  total_occurrences: number
  verified_count: number
  verified_pct: number
  agreed_exact_count: number
  agreed_exact_pct: number
  agreed_under_order_count: number
  agreed_under_order_pct: number
}

// Accepts an arbitrary filter map so the occurrence list page's filter state
// can be threaded through unchanged (deployment, event, taxon, score
// thresholds, apply_defaults, etc).
export const useHumanModelAgreement = (
  projectId?: string,
  filters?: Record<string, string | number | boolean | undefined>
) => {
  const url = `${API_URL}/${API_ROUTES.OCCURRENCES}/stats/human-model-agreement/`

  const params = new URLSearchParams()
  if (projectId) params.set('project_id', projectId)
  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== '' && value !== null) {
        params.set(key, String(value))
      }
    })
  }

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<Response>({
    queryKey: [
      API_ROUTES.OCCURRENCES,
      'stats',
      'human-model-agreement',
      projectId,
      filters,
    ],
    url: `${url}?${params.toString()}`,
  })

  return {
    data,
    isLoading,
    isFetching,
    error,
  }
}
