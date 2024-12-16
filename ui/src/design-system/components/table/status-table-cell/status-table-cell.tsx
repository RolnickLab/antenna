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
    {details?.length ? (
      <Tooltip content={details}>
        <div>
          <StatusMarker color={color} />
        </div>
      </Tooltip>
    ) : (
      <StatusMarker color={color} />
    )}
    <span className={styles.label}>{label}</span>
  </div>
)
