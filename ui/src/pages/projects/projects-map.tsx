import { ErrorState } from 'components/error-state/error-state'
import { DEFAULT_ZOOM } from 'components/map/config'
import { MultiMarkerMap } from 'components/map/multi-marker-map/multi-marker-map'
import { Project } from 'data-services/models/project'
import { InfoBlock } from 'nova-ui-kit'
import { useMemo } from 'react'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const ProjectsMap = ({
  error,
  isLoading,
  projects = [],
}: {
  error?: any
  isLoading: boolean
  projects?: Project[]
}) => {
  const markers = useMemo(
    () =>
      projects.flatMap((project) =>
        project.location
          ? [
              {
                position: project.location,
                popupContent: <ProjectsMapPopupContent project={project} />,
              },
            ]
          : []
      ),
    [projects]
  )

  if (error) {
    return <ErrorState error={error} />
  }

  return (
    <MultiMarkerMap
      className="h-[calc(100vh-320px)] min-h-[400px]"
      isLoading={isLoading}
      markers={markers}
      // A project marker is a mean position, so street level would mislead.
      maxZoom={DEFAULT_ZOOM}
    />
  )
}

const ProjectsMapPopupContent = ({ project }: { project: Project }) => (
  <InfoBlock
    fields={[
      {
        label: translate(STRING.FIELD_LABEL_PROJECT),
        value: project.name,
        to: APP_ROUTES.PROJECT_DETAILS({ projectId: project.id }),
      },
      {
        label: translate(STRING.NAV_ITEM_DEPLOYMENTS),
        value: project.numDeployments,
      },
    ]}
  />
)
