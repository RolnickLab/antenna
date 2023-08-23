import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { Project, ServerProject } from 'data-services/models/project'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { COLLECTION } from './constants'

const convertServerRecord = (record: ServerProject) => new Project(record)

export const useProjects = (
  params?: FetchParams
): {
  projects?: Project[]
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
        .get<{ results: ServerProject[]; count: number }>(fetchUrl)
        .then((res) => ({
          results: res.data.results.map(convertServerRecord),
          count: res.data.count,
        })),
  })

  return {
    projects: data?.results,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
