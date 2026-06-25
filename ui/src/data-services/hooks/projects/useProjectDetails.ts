import { API_ROUTES, API_URL } from 'data-services/constants'
import { ServerProject } from 'data-services/models/project'
import { ProjectDetails } from 'data-services/models/project-details'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerProject) =>
  new ProjectDetails(record)

export const useProjectDetails = (
  projectId: string,
  useInternalCache?: boolean
): {
  project?: ProjectDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<ProjectDetails>({
      queryKey: [API_ROUTES.PROJECTS, projectId],
      url: `${API_URL}/${API_ROUTES.PROJECTS}/${projectId}/?with_charts=false`,
      staleTime: useInternalCache ? Infinity : undefined,
    })

  const project = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    project,
    isLoading,
    isFetching,
    error,
  }
}
