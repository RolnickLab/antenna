import { useDeployments } from 'data-services/hooks/deployments/useDeployments'
import { MultiMarkerMap } from 'design-system/map/multi-marker-map/multi-marker-map'
import { MarkerPosition } from 'design-system/map/types'
import { useMemo } from 'react'
import { DeploymentsMapPopupContent } from './deployments-map-popup-content'

export const DeploymentsMap = () => {
  const { deployments, isLoading } = useDeployments()

  const markers = useMemo(() => {
    if (!deployments) {
      return []
    }

    return deployments.map((deployment) => ({
      position: new MarkerPosition(deployment.latitude, deployment.longitude),
      popupContent: <DeploymentsMapPopupContent deployment={deployment} />,
    }))
  }, [deployments])

  return <MultiMarkerMap isLoading={isLoading} markers={markers} />
}
