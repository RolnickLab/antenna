import classNames from 'classnames'
import _ from 'lodash'
import { CSSProperties, ReactNode } from 'react'
import { CellTheme, TextAlign } from '../types'
import styles from './basic-table-cell.module.scss'

interface BasicTableCellProps {
  value?: string | number
  details?: string[]
  theme?: CellTheme
  children?: ReactNode
  style?: CSSProperties
}

export const BasicTableCell = ({
  value,
  details,
  theme = CellTheme.Default,
  children,
  style = {},
}: BasicTableCellProps) => {
  const textAlign = _.isNumber(value) ? TextAlign.Right : TextAlign.Left
  const label = _.isNumber(value) ? value.toLocaleString() : value

  return (
    <div
      className={classNames(styles.tableCell, {
        [styles.primary]: theme === CellTheme.Primary,
        [styles.bubble]: theme === CellTheme.Bubble,
      })}
      style={{ textAlign, ...style }}
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
