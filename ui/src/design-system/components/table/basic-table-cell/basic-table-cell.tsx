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
  const isNumber = _.isNumber(value)
  const textAlign = isNumber ? TextAlign.Right : TextAlign.Left
  const label = isNumber ? value.toLocaleString('en-US') : value

  return (
    <div
      className={classNames(styles.tableCell, {
        [styles.primary]: theme === CellTheme.Primary,
      })}
      style={{ textAlign }}
    >
      <span>{label}</span>
    </div>
  )
}
