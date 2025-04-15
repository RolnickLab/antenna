import { API_ROUTES, API_URL, REFETCH_INTERVAL } from 'data-services/constants'
import { Export, ServerExport } from 'data-services/models/export'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerExport) => new Export(record)

export const useExportDetails = (
  id: string
): {
  exportDetails?: Export
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<Export>({
    queryKey: [API_ROUTES.EXPORTS, id],
    url: `${API_URL}/${API_ROUTES.EXPORTS}/${id}/`,
    refetchInterval: REFETCH_INTERVAL,
  })

  const exportDetails = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    exportDetails,
    isLoading,
    isFetching,
    error,
  }
}
