import classNames from 'classnames'
import { Status } from '../types'
import styles from './status-marker.module.scss'

const statusClasses: { [key in Status]: string } = {
  [Status.Success]: styles.success,
  [Status.Warning]: styles.warning,
  [Status.Error]: styles.error,
  [Status.Neutral]: styles.neutral,
}

export const StatusMarker = ({ status }: { status: Status }) => (
  <div className={classNames(styles.statusMarker, statusClasses[status])} />
)
