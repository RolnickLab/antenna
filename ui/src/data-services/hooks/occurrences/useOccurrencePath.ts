import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  convertPathFrame,
  PathFrame,
  ServerOccurrencePathFrame,
} from 'data-services/models/occurrence-path'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

/**
 * Where an occurrence was in every frame it appears in, earliest first.
 *
 * `enabled` is the point of this hook: a session holds thousands of occurrences and
 * a path is only worth fetching when a person asks for one. Once fetched it is kept,
 * so stepping between captures redraws the same path rather than requesting it again.
 */
export const useOccurrencePath = (
  occurrenceId?: string,
  enabled?: boolean
): {
  path?: PathFrame[]
  isLoading: boolean
  error?: unknown
} => {
  const { data, isLoading, error } = useAuthorizedQuery<
    ServerOccurrencePathFrame[]
  >({
    enabled: !!occurrenceId && !!enabled,
    queryKey: [API_ROUTES.OCCURRENCES, occurrenceId, 'path'],
    staleTime: Infinity,
    url: `${API_URL}/${API_ROUTES.OCCURRENCES}/${occurrenceId}/path/`,
  })

  const path = useMemo(() => data?.map(convertPathFrame), [data])

  return {
    path,
    isLoading: !!occurrenceId && !!enabled && isLoading,
    error,
  }
}
