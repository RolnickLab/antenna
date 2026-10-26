import { BasicTooltip, StatusMarker } from 'nova-ui-kit'
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
    <BasicTooltip content={details}>
      <div className={styles.content}>
        <StatusMarker color={color} />
        <span className={styles.label}>{label}</span>
      </div>
    </BasicTooltip>
  </div>
)
