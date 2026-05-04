import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  ProcessingService,
  ServerProcessingService,
} from 'data-services/models/processing-service'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerProcessingService) =>
  new ProcessingService(record)

export const useProcessingServiceDetails = (
  id: string,
  projectId: string
): {
  processingService?: ProcessingService
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<ProcessingService>({
      queryKey: [API_ROUTES.PROCESSING_SERVICES, id, projectId],
      url: `${API_URL}/${API_ROUTES.PROCESSING_SERVICES}/${id}/?project_id=${projectId}`,
    })

  const processingService = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    processingService: processingService,
    isLoading,
    isFetching,
    error,
  }
}
