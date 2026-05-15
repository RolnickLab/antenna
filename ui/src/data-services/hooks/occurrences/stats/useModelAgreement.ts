import { API_ROUTES, API_URL } from 'data-services/constants'
import { useAuthorizedQuery } from '../../auth/useAuthorizedQuery'

interface ModelAgreementResponse {
  project_id: number
  total_occurrences: number
  verified_count: number
  verified_pct: number
  verified_with_prediction_count: number
  no_prediction_count: number
  agreed_exact_count: number
  agreed_exact_pct: number
  agreed_under_order_count: number
  agreed_under_order_pct: number
}

// Accepts an arbitrary filter map so the occurrence list page's filter state
// can be threaded through unchanged (deployment, event, taxon, score
// thresholds, apply_defaults, etc).
export const useModelAgreement = (
  projectId?: string,
  filters?: Record<string, string | number | boolean | undefined>
) => {
  const url = `${API_URL}/${API_ROUTES.OCCURRENCES}/stats/model-agreement/`

  const params = new URLSearchParams()
  if (projectId) params.set('project_id', projectId)
  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== '' && value !== null) {
        params.set(key, String(value))
      }
    })
  }

  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<ModelAgreementResponse>({
      queryKey: [
        API_ROUTES.OCCURRENCES,
        'stats',
        'model-agreement',
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
