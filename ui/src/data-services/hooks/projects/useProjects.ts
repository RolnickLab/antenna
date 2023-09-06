import { API_ROUTES } from 'data-services/constants'
import { Project, ServerProject } from 'data-services/models/project'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerProject) => new Project(record)

export const useProjects = (): {
  projects?: Project[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.PROJECTS })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerProject[]
    count: number
  }>({
    queryKey: [API_ROUTES.PROJECTS],
    url: fetchUrl,
  })

  const projects = useMemo(() => data?.results.map(convertServerRecord), [data])

  return {
    projects,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
