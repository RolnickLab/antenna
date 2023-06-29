import classNames from 'classnames'
import { Status } from '../types'
import styles from './status-bar.module.scss'

const statusClasses: { [key in Status]: string } = {
  [Status.Success]: styles.success,
  [Status.Warning]: styles.warning,
  [Status.Error]: styles.error,
}

export const StatusBar = ({
  description,
  progress,
  status,
}: {
  description?: string
  progress: number // Value in range [0,1]
  status: Status
}) => {
  if (progress < 0 || progress > 1) {
    throw Error(
      `Property progress has value ${progress}, but must in range [0,1].`
    )
  }

  return (
    <div>
      <div className={styles.barBackground}>
        <div
          style={{ width: `${(progress / 1) * 100}%` }}
          className={classNames(styles.bar, statusClasses[status])}
        />
      </div>
      {description?.length ? (
        <p className={styles.description}>{description}</p>
      ) : null}
    </div>
  )
}
