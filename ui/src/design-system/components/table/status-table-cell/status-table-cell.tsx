import { StatusMarker } from 'design-system/components/status/status-marker/status-marker'
import { Status } from 'design-system/components/status/types'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import styles from './status-table-cell.module.scss'

interface StatusTableCellProps {
  details?: string
  label: string
  status: Status
}

export const StatusTableCell = ({
  details,
  label,
  status,
}: StatusTableCellProps) => (
  <div className={styles.tableCell}>
    {details?.length ? (
      <Tooltip content={details}>
        <div>
          <StatusMarker status={status} />
        </div>
      </Tooltip>
    ) : (
      <StatusMarker status={status} />
    )}
    <span className={styles.label}>{label}</span>
  </div>
)
