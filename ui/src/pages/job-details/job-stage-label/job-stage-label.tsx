import { StatusMarker } from 'design-system/components/status/status-marker/status-marker'
import { Status } from 'design-system/components/status/types'
import styles from './job-stage-label.module.scss'

export const JobStageLabel = ({
  label,
  status,
}: {
  label: string
  status?: Status
}) => (
  <div className={styles.container}>
    <span className={styles.label}>{label}</span>
    {status ? <StatusMarker status={status} /> : null}
  </div>
)
