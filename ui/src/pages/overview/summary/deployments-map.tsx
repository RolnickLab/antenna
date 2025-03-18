import { Deployment } from 'data-services/models/deployment'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import { MultiMarkerMap } from 'design-system/map/multi-marker-map/multi-marker-map'
import { MarkerPosition } from 'design-system/map/types'
import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const DeploymentsMap = ({
  deployments,
}: {
  deployments: Deployment[]
}) => {
  const markers = useMemo(
    () =>
      deployments.map((deployment) => ({
        position: new MarkerPosition(deployment.latitude, deployment.longitude),
        popupContent: <DeploymentsMapPopupContent deployment={deployment} />,
      })),
    [deployments]
  )

  return <MultiMarkerMap markers={markers} />
}

const DeploymentsMapPopupContent = ({
  deployment,
}: {
  deployment: Deployment
}) => {
  const { projectId } = useParams()

  return (
    <InfoBlock
      fields={[
        {
          label: translate(STRING.FIELD_LABEL_DEPLOYMENT),
          value: deployment.name,
          to: APP_ROUTES.DEPLOYMENT_DETAILS({
            projectId: projectId as string,
            deploymentId: deployment.id,
          }),
        },
        {
          label: translate(STRING.FIELD_LABEL_SESSIONS),
          value: deployment.numEvents,
        },
      ]}
    />
  )
}
