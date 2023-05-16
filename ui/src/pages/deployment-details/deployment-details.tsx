import { Deployment } from 'data-services/models/deployment'
import * as Dialog from 'design-system/components/dialog/dialog'
import { Input, InputValue } from 'design-system/components/input/input'
import { Map, MarkerPosition } from 'design-system/map/map'
import _ from 'lodash'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './deployment-details.module.scss'
import { DeploymentMap } from './deployment-map'

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
  )
}
