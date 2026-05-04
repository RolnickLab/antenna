import { StatusMarker } from 'design-system/components/status/status-marker/status-marker'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
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
  <BasicTooltip content={details}>
    <div className={styles.container}>
      <span className={styles.label}>{label}</span>
      <StatusMarker color={color} />
    </div>
  </BasicTooltip>
)
