import classNames from 'classnames'
import _ from 'lodash'
import { CellTheme, TextAlign } from '../types'
import styles from './basic-table-cell.module.scss'
import { ReactNode } from 'react'

interface BasicTableCellProps {
  value?: string | number
  details?: string[]
  theme?: CellTheme
  children?: ReactNode
}

export const BasicTableCell = ({
  value,
  details,
  theme = CellTheme.Default,
  children,
}: BasicTableCellProps) => {
  const textAlign = _.isNumber(value) ? TextAlign.Right : TextAlign.Left
  const label = _.isNumber(value) ? value.toLocaleString() : value

  return (
    <div
      className={classNames(styles.tableCell, {
        [styles.primary]: theme === CellTheme.Primary,
      })}
      style={{ textAlign }}
    >
      {label && <span className={styles.label}>{label}</span>}
      {details &&
        details.map((detail, index) => (
          <span key={index} className={styles.details}>
            {detail}
          </span>
        ))}
      {children}
    </div>
  )
}
