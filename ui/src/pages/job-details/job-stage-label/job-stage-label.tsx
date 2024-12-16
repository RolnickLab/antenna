import { StatusMarker } from 'design-system/components/status/status-marker/status-marker'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import styles from './job-stage-label.module.scss'

export const JobStageLabel = ({
  color,
  details,
  label,
}: {
  color: string
  details?: string
  label: string
}) => (
  <div className={styles.container}>
    <span className={styles.label}>{label}</span>
    {details?.length ? (
      <Tooltip content={details}>
        <div>
          <StatusMarker color={color} />
        </div>
      </Tooltip>
    ) : (
      <StatusMarker color={color} />
    )}
  </div>
)
