import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { useParams } from 'react-router-dom'
import { hasProjectFeature, ProjectFeature } from './project-features'

export const useProjectFeature = (feature: ProjectFeature) => {
  const { projectId } = useParams()
  const { project } = useProjectDetails(projectId as string, true)

  return hasProjectFeature(project?.featureFlags, feature)
}
