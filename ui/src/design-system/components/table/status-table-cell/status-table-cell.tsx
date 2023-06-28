import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { CellStatus } from '../types'
import { StatusMarker } from './status-marker/status-marker'
import styles from './status-table-cell.module.scss'

interface StatusTableCellProps {
  details?: string
  label: string
  status: CellStatus
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
    ) : null}
    <span className={styles.label}>{label}</span>
  </div>
)
