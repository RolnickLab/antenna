import { Deployment } from 'data-services/models/deployment'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputValue } from 'design-system/components/input/input'
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
      <Dialog.Header title="Deployment details" />
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
            <InputValue label="Deployment ID" value={deployment.id} />
            <InputValue label="Name" value={deployment.name} />
          </div>
          <div className={styles.sectionRow}>
            <InputValue label="Device" value="WIP" />
            <InputValue label="Site" value="WIP" />
          </div>
        </div>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Location</h2>
        <div className={styles.sectionContent}>
          <div className={styles.sectionRow}>
            <InputValue label="Latitude" value="WIP" />
            <InputValue label="Latitude" value="WIP" />
          </div>
        </div>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Source images</h2>
        <div className={styles.sectionContent}>
          <div className={styles.sectionRow}>
            <InputValue label="Path" value="WIP" />
            <InputValue label="Connection status" value="WIP" />
          </div>
          <div className={styles.sectionRow}>
            <InputValue label="Images" value={deployment.numImages} />
            <InputValue label="Sessions" value={deployment.numEvents} />
          </div>
          <div className={styles.sectionRow}>
            <InputValue label="Occurrences" value="WIP" />
            <InputValue label="Detections" value={deployment.numDetections} />
          </div>
        </div>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Processing</h2>
        <div className={styles.sectionContent}>
          <div className={styles.sectionRow}>
            <InputValue label="Localization model" value="WIP" />
            <InputValue label="Localization batch size" value="WIP" />
          </div>
          <div className={styles.sectionRow}>
            <InputValue label="Binary classification model" value="WIP" />
          </div>
          <div className={styles.sectionRow}>
            <InputValue label="Species classification model" value="WIP" />
            <InputValue label="Classification batch size" value="WIP" />
          </div>
          <div className={styles.sectionRow}>
            <InputValue label="Occurrence tracking algorithm" value="WIP" />
          </div>
        </div>
      </div>
    </div>
  )
}
