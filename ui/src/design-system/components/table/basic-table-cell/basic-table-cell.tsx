import classNames from 'classnames'
import _ from 'lodash'
import { CellTheme, TextAlign } from '../types'
import styles from './basic-table-cell.module.scss'

interface BasicTableCellProps {
  value: string | number
  details?: string
  theme?: CellTheme
}

export const BasicTableCell = ({
  value,
  details,
  theme = CellTheme.Default,
}: BasicTableCellProps) => {
  const isNumber = _.isNumber(value)
  const textAlign = isNumber ? TextAlign.Right : TextAlign.Left
  const label = isNumber ? value.toLocaleString() : value

  return (
    <div
      className={classNames(styles.tableCell, {
        [styles.primary]: theme === CellTheme.Primary,
      })}
      style={{ textAlign }}
    >
      <span className={styles.label}>{label}</span>
      {details && <span className={styles.details}>{details}</span>}
    </div>
  )
}
