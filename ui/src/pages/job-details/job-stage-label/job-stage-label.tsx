import { StatusMarker } from 'design-system/components/status/status-marker/status-marker'
import { Status } from 'design-system/components/status/types'
import styles from './job-stage-label.module.scss'
import { Tooltip } from 'design-system/components/tooltip/tooltip'

export const JobStageLabel = ({
  details,
  label,
  status,
}: {
  details: string
  label: string
  status?: Status
}) => (
  <Tooltip content={details}>
    <div className={styles.container}>
      <span className={styles.label}>{label}</span>
      {status ? <StatusMarker status={status} /> : null}
    </div>
  </Tooltip>
)
