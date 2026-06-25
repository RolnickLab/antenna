import classNames from 'classnames'
import styles from './badge.module.scss'

export const Badge = ({
  deprecated,
  label,
}: {
  deprecated?: boolean
  label: string
}) => (
  <div
    className={classNames(styles.badge, {
      [styles.deprecated]: deprecated,
    })}
  >
    {label}
  </div>
)
