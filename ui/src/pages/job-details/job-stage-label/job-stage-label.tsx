import { StatusMarker } from 'design-system/components/status/status-marker/status-marker'
import { Status } from 'design-system/components/status/types'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import styles from './job-stage-label.module.scss'

export const JobStageLabel = ({
  label,
  status,
  statusDetails,
}: {
  label: string
  status: Status
  statusDetails?: string
}) => (
  <div className={styles.container}>
    <span className={styles.label}>{label}</span>
    {statusDetails?.length ? (
      <Tooltip content={statusDetails}>
        <div>
          <StatusMarker status={status} />
        </div>
      </Tooltip>
    ) : (
      <StatusMarker status={status} />
    )}
  </div>
)
