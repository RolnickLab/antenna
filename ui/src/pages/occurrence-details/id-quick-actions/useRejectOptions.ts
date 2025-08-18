import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { useParams } from 'react-router-dom'

export const useRejectOptions = () => {
  const { projectId } = useParams()
  const { project } = useProjectDetails(projectId as string, true)
  const rejectOptions =
    project?.defaultFilters.excludeTaxa.map((taxon) => ({
      value: taxon.id,
      label: taxon.name,
    })) ?? []

  return { rejectOptions }
}
