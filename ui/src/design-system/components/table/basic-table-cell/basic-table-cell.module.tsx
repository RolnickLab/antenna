import classNames from 'classnames'
import _ from 'lodash'
import { CellTheme, TextAlign } from '../types'
import styles from './basic-table-cell.module.scss'

interface BasicTableCellProps {
  value: string | number
  theme?: CellTheme
}

export const BasicTableCell = ({
  value,
  theme = CellTheme.Default,
}: BasicTableCellProps) => {
  const textAlign = _.isNumber(value) ? TextAlign.Right : TextAlign.Left

  return (
    <div
      className={classNames(styles.tableCell, {
        [styles.primary]: theme === CellTheme.Primary,
      })}
      style={{ textAlign }}
    >
      <span>{value}</span>
    </div>
  )
}
