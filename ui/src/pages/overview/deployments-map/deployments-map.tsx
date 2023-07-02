import { useDeployments } from 'data-services/hooks/useDeployments'
import { MultiMarkerMap } from 'design-system/map/multi-marker-map/multi-marker-map'
import { MarkerPosition } from 'design-system/map/types'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const DeploymentsMap = () => {
  const { deployments, isLoading } = useDeployments()

  const markers = useMemo(() => {
    if (!deployments) {
      return []
    }

    return deployments.map((deployment) => {
      const position = new MarkerPosition(
        deployment.latitude,
        deployment.longitude
      )
      const popupContent = (
        <>
          <p>
            <Link to={`/deployments/${deployment.id}`}>
              <span>{deployment.name}</span>
            </Link>
          </p>
          <p>
            <span>
              {translate(STRING.DETAILS_LABEL_SESSIONS)}: {deployment.numEvents}
            </span>
            <br />
            <span>
              {translate(STRING.DETAILS_LABEL_IMAGES)}: {deployment.numImages}
            </span>
            <br />
            <span>
              {translate(STRING.DETAILS_LABEL_DETECTIONS)}:{' '}
              {deployment.numDetections}
            </span>
          </p>
        </>
      )

      return { position, popupContent }
    })
  }, [deployments])

  return <MultiMarkerMap isLoading={isLoading} markers={markers} />
}
