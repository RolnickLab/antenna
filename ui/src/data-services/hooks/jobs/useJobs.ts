import { API_ROUTES } from 'data-services/constants'
import { Job, ServerJob } from 'data-services/models/job'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerJob) => new Job(record)

export const useJobs = (
  params?: FetchParams
): {
  jobs?: Job[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.JOBS, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerJob[]
    count: number
  }>({
    queryKey: [API_ROUTES.JOBS, params],
    url: fetchUrl,
  })

  const jobs = useMemo(() => data?.results.map(convertServerRecord), [data])

  return {
    jobs,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
