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
  agreed_exact_ci_low: number | null
  agreed_exact_ci_high: number | null
  agreed_any_rank_count: number
  agreed_any_rank_pct: number
  agreed_any_rank_ci_low: number | null
  agreed_any_rank_ci_high: number | null
  // Cohen's kappa (exact-taxon) — agreement beyond chance. Range [-1, 1];
  // null when denominator is 0 or expected agreement is 1.0.
  cohens_kappa: number | null
  // Only populated when the caller passes ?agreement_coarsest_rank=<RANK>.
  agreement_coarsest_rank: string | null
  agreed_coarser_rank_count: number | null
  agreed_coarser_rank_pct: number | null
}

type FilterPrimitive = string | number | boolean
type FilterValue = FilterPrimitive | FilterPrimitive[] | null | undefined

// Accepts an arbitrary filter map so the occurrence list page's filter state
// can be threaded through unchanged (deployment, event, taxon, score
// thresholds, apply_defaults, etc). Arrays are appended as repeated query
// params so multi-select filters (e.g. `algorithm`, `not_algorithm`, which
// the backend reads via `request.query_params.getlist(...)`) survive.
export const useModelAgreement = (
  projectId?: string,
  filters?: Record<string, FilterValue>
) => {
  const url = `${API_URL}/${API_ROUTES.OCCURRENCES}/stats/model-agreement/`

  const params = new URLSearchParams()
  if (projectId) params.set('project_id', projectId)
  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return
      if (Array.isArray(value)) {
        value.forEach((item) => {
          if (item !== undefined && item !== null && item !== '') {
            params.append(key, String(item))
          }
        })
        return
      }
      params.set(key, String(value))
    })
  }
  const queryString = params.toString()

  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<ModelAgreementResponse>({
      queryKey: [
        API_ROUTES.OCCURRENCES,
        'stats',
        'model-agreement',
        projectId,
        queryString,
      ],
      url: `${url}?${queryString}`,
    })

  return {
    data,
    isLoading,
    isFetching,
    error,
  }
}
