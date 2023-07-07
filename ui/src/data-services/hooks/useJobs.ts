import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { Job, ServerJob } from 'data-services/models/job'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'

const convertServerRecord = (record: ServerJob) => new Job(record)

const COLLECTION = 'jobs'

export const useJobs = (
  params?: FetchParams
): {
  jobs?: Job[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: COLLECTION, params })

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, params],
    queryFn: () =>
      axios
        .get<{ results: ServerJob[]; count: number }>(fetchUrl)
        .then((res) => ({
          results: res.data.results.map(convertServerRecord),
          count: res.data.count,
        })),
  })

  return {
    jobs: data?.results,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
