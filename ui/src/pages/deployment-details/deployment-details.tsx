import { Deployment } from 'data-services/models/deployment'
import { Button } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputValue } from 'design-system/components/input/input'
import { Map, MarkerPosition } from 'design-system/map/map'
import { useMemo } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './deployment-details.module.scss'

export const DeploymentDetails = ({
  deployment,
  onEditClick,
}: {
  deployment: Deployment
  onEditClick: () => void
}) => (
  <>
    <Dialog.Header title={translate(STRING.DETAILS_LABEL_DEPLOYMENT_DETAILS)}>
      <div className={styles.buttonWrapper}>
        <Button label={translate(STRING.EDIT)} onClick={onEditClick} />
      </div>
    </Dialog.Header>
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
          <div className={styles.sectionRow}>
            <InputValue
              label={translate(STRING.DETAILS_LABEL_LATITUDE)}
              value={deployment.location.lat}
            />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_LONGITUDE)}
              value={deployment.location.lng}
            />
          </div>
          <DeploymentMap deployment={deployment} />
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
              value={deployment.path}
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
  </>
)

const DeploymentMap = ({ deployment }: { deployment: Deployment }) => {
  const markerPosition = useMemo(
    () => new MarkerPosition(deployment.location.lat, deployment.location.lng),
    []
  )

  return <Map center={markerPosition} markerPosition={markerPosition} />
}
