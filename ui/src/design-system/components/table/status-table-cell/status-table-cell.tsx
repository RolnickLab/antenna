import { StatusMarker } from 'design-system/components/status/status-marker/status-marker'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import styles from './status-table-cell.module.scss'

interface StatusTableCellProps {
  color: string
  details?: string
  label: string
}

export const StatusTableCell = ({
  color,
  details,
  label,
}: StatusTableCellProps) => (
  <div className={styles.tableCell}>
    <Tooltip content={details}>
      <div className={styles.content}>
        <StatusMarker color={color} />
        <span className={styles.label}>{label}</span>
      </div>
    </Tooltip>
  </div>
)
