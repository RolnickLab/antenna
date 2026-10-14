import { API_ROUTES, API_URL } from 'data-services/constants'
import { ServerOccurrenceHistoryEntry } from 'data-services/models/occurrence-history'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

// Under the occurrences prefix, so every mutation that invalidates occurrences refreshes it.
export const getOccurrenceHistoryQueryKey = (occurrenceId: string) => [
  API_ROUTES.OCCURRENCES,
  occurrenceId,
  'history',
]

export const useOccurrenceHistory = ({
  occurrenceId,
  projectId,
}: {
  occurrenceId: string
  projectId?: string
}): {
  entries?: ServerOccurrenceHistoryEntry[]
  isLoading: boolean
  error?: unknown
} => {
  const params = new URLSearchParams(projectId ? { project_id: projectId } : {})
  const { data, isLoading, error } = useAuthorizedQuery<
    ServerOccurrenceHistoryEntry[]
  >({
    enabled: !!occurrenceId,
    queryKey: getOccurrenceHistoryQueryKey(occurrenceId),
    url: `${API_URL}/${API_ROUTES.OCCURRENCES}/${occurrenceId}/history/?${params}`,
  })

  return { entries: data, isLoading, error }
}
