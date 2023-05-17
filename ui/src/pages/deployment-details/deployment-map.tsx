import { Input, InputValue } from 'design-system/components/input/input'
import { Map, MarkerPosition } from 'design-system/map/map'
import _ from 'lodash'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './deployment-details.module.scss'

export const DeploymentMap = ({ editable }: { editable?: boolean }) => {
  const markerPosition = new MarkerPosition(52.30767, 5.04011)

  if (!editable) {
    return <StaticDeploymentMap markerPosition={markerPosition} />
  }

  return <EditableDeploymentMap defaultValue={markerPosition} />
}

const StaticDeploymentMap = ({
  markerPosition,
}: {
  markerPosition: MarkerPosition
}) => {
  return (
    <>
      <div className={styles.sectionRow}>
        <InputValue
          label={translate(STRING.DETAILS_LABEL_LATITUDE)}
          value={markerPosition.lat}
        />
        <InputValue
          label={translate(STRING.DETAILS_LABEL_LONGITUDE)}
          value={markerPosition.lng}
        />
      </div>
      <Map center={markerPosition} markerPosition={markerPosition} />
    </>
  )
}

const EditableDeploymentMap = ({
  defaultValue,
}: {
  defaultValue: MarkerPosition
}) => {
  const [markerPosition, setMarkerPosition] = useState(defaultValue)
  const [lat, setLat] = useState(markerPosition.lat)
  const [lng, setLng] = useState(markerPosition.lng)

  return (
    <>
      <div className={styles.sectionRow}>
        <Input
          name="latitude"
          label={translate(STRING.DETAILS_LABEL_LATITUDE)}
          type="number"
          value={lat}
          onChange={(e) => {
            const lat = _.toNumber(e.currentTarget.value)
            setLat(lat)
          }}
          onBlur={() => setMarkerPosition(new MarkerPosition(lat, lng))}
        />
        <Input
          name="longitude"
          label={translate(STRING.DETAILS_LABEL_LONGITUDE)}
          type="number"
          value={lng}
          onChange={(e) => {
            const lng = _.toNumber(e.currentTarget.value)
            setLat(lng)
          }}
          onBlur={() => setMarkerPosition(new MarkerPosition(lat, lng))}
        />
      </div>
      <Map
        center={markerPosition}
        markerPosition={markerPosition}
        markerDraggable
        onMarkerPositionChange={(markerPosition) => {
          const updatedLat = _.round(markerPosition.lat, 5)
          const updatedLng = _.round(markerPosition.lng, 5)

          setMarkerPosition(new MarkerPosition(updatedLat, updatedLng))
          setLat(updatedLat)
          setLng(updatedLng)
        }}
      />
    </>
  )
}
