import { API_ROUTES } from 'data-services/constants'
import { Pipeline, ServerPipeline } from 'data-services/models/pipeline'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerPipeline) => new Pipeline(record)

export const usePipelines = (
  params?: FetchParams
): {
  pipelines?: Pipeline[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.PIPELINES, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerPipeline[]
    count: number
  }>({
    queryKey: [API_ROUTES.PIPELINES, params],
    url: fetchUrl,
  })

  const pipelines = useMemo(
    () => data?.results.map(convertServerRecord),
    [data]
  )

  return {
    pipelines,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
