import { API_ROUTES, API_URL } from 'data-services/constants'
import { Project, ServerProject } from 'data-services/models/project'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerProject) => new Project(record)

export const useProjectDetails = (
  projectId: string
): {
  project?: Project
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<Project>({
    queryKey: [API_ROUTES.PROJECTS, projectId],
    url: `${API_URL}/${API_ROUTES.PROJECTS}/${projectId}`,
  })

  return {
    project: data ? convertServerRecord(data) : undefined,
    isLoading,
    isFetching,
    error,
  }
}
