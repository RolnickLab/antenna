import { API_ROUTES, API_URL } from 'data-services/constants'
import { Backend, ServerBackend } from 'data-services/models/backend'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerBackend) => new Backend(record)

export const useBackendDetails = (
  backendId: string
): {
  backend?: Backend
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<Backend>({
    queryKey: [API_ROUTES.BACKENDS, backendId],
    url: `${API_URL}/${API_ROUTES.BACKENDS}/${backendId}/`,
  })

  const backend = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    backend,
    isLoading,
    isFetching,
    error,
  }
}
