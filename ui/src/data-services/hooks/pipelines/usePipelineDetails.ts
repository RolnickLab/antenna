import { API_ROUTES, API_URL } from 'data-services/constants'
import { Pipeline, ServerPipeline } from 'data-services/models/pipeline'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerPipeline) => new Pipeline(record)

export const usePipelineDetails = (
  pipelineId: string
): {
  pipeline?: Pipeline
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<Pipeline>({
    queryKey: [API_ROUTES.PIPELINES, pipelineId],
    url: `${API_URL}/${API_ROUTES.PIPELINES}/${pipelineId}/`,
  })

  const pipeline = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    pipeline,
    isLoading,
    isFetching,
    error,
  }
}
