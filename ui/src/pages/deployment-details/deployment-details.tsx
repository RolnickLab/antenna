import { Deployment } from 'data-services/models/deployment'
import * as Dialog from 'design-system/components/dialog/dialog'
import { Input, InputValue } from 'design-system/components/input/input'
import { Map, MarkerPosition } from 'design-system/map/map'
import _ from 'lodash'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './deployment-details.module.scss'

export const DeploymentDetailsDialog = ({
  deployment,
  open,
  onOpenChange,
}: {
  deployment?: Deployment
  open: boolean
  onOpenChange: () => void
}) => (
  <Dialog.Root open={open} onOpenChange={onOpenChange}>
    <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
      <Dialog.Header
        title={translate(STRING.DETAILS_LABEL_DEPLOYMENT_DETAILS)}
      />
      <DeploymentDetails deployment={deployment} />
    </Dialog.Content>
  </Dialog.Root>
)

const DeploymentDetails = ({ deployment }: { deployment?: Deployment }) => {
  if (!deployment) {
    return null
  }

  return (
    <div className={styles.content}>
      <div className={styles.section}>
        <div className={styles.sectionContent}>
          <div className={styles.sectionRow}>
            <InputValue
              label={translate(STRING.DETAILS_LABEL_DEPLOYMENT_ID)}
              value={deployment.id}
            />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_NAME)}
              value={deployment.name}
            />
          </div>
          <div className={styles.sectionRow}>
            <InputValue
              label={translate(STRING.DETAILS_LABEL_DEVICE)}
              value="WIP"
            />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_SITE)}
              value="WIP"
            />
          </div>
        </div>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>
          {translate(STRING.DETAILS_LABEL_LOCATION)}
        </h2>
        <div className={styles.sectionContent}>
          <DeploymentMap />
        </div>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>
          {translate(STRING.DETAILS_LABEL_SOURCE_IMAGES)}
        </h2>
        <div className={styles.sectionContent}>
          <div className={styles.sectionRow}>
            <InputValue
              label={translate(STRING.DETAILS_LABEL_PATH)}
              value="WIP"
            />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_CONNECTION_STATUS)}
              value="WIP"
            />
          </div>
          <div className={styles.sectionRow}>
            <InputValue
              label={translate(STRING.DETAILS_LABEL_IMAGES)}
              value={deployment.numImages}
            />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_SESSIONS)}
              value={deployment.numEvents}
            />
          </div>
          <div className={styles.sectionRow}>
            <InputValue
              label={translate(STRING.DETAILS_LABEL_OCCURRENCES)}
              value="WIP"
            />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_DETECTIONS)}
              value={deployment.numDetections}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

const DeploymentMap = ({ editable }: { editable?: boolean }) => {
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
          onChange={(lat) => setLat(lat as number)}
          onBlur={() => setMarkerPosition(new MarkerPosition(lat, lng))}
        />
        <Input
          name="longitude"
          label={translate(STRING.DETAILS_LABEL_LONGITUDE)}
          type="number"
          value={lng}
          onChange={(lng) => setLng(lng as number)}
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
