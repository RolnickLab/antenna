import { API_ROUTES } from 'data-services/constants'
import { Project, ServerProject } from 'data-services/models/project'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

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
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.PROJECTS, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerProject[]
    count: number
  }>({
    queryKey: [API_ROUTES.PROJECTS, params],
    url: fetchUrl,
  })

  return {
    projects: data?.results.map(convertServerRecord),
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
