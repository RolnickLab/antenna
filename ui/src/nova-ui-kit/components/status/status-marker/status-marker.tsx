import classNames from 'classnames'
import styles from './status-marker.module.scss'

export const StatusMarker = ({ color }: { color: string }) => (
  <div
    className={classNames(styles.statusMarker)}
    style={{ backgroundColor: color }}
  />
)
