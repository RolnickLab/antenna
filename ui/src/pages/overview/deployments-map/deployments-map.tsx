import { Deployment } from 'data-services/models/deployment'
import { MultiMarkerMap } from 'design-system/map/multi-marker-map/multi-marker-map'
import { MarkerPosition } from 'design-system/map/types'
import { useMemo } from 'react'
import { DeploymentsMapPopupContent } from './deployments-map-popup-content'

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
