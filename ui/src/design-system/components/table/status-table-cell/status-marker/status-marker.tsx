import classNames from 'classnames'
import { CellStatus } from '../../types'
import styles from './status-marker.module.scss'

const statusClasses: { [key in CellStatus]: string } = {
  [CellStatus.Success]: styles.success,
  [CellStatus.Warning]: styles.warning,
  [CellStatus.Error]: styles.error,
}

export const StatusMarker = ({ status }: { status: CellStatus }) => (
  <div className={classNames(styles.statusMarker, statusClasses[status])} />
)
