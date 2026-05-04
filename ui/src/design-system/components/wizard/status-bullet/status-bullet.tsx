import classNames from 'classnames'
import styles from './status-bullet.module.scss'

export enum StatusBulletTheme {
  Default = 'default',
  Success = 'success',
  Neutral = 'neutral',
}

interface StatusBulletProps {
  Icon?: React.ComponentType<{
    className?: string
  }>
  theme?: StatusBulletTheme
  value?: number
}

export const StatusBullet = ({
  theme = StatusBulletTheme.Default,
  value,
  Icon,
}: StatusBulletProps) => (
  <div
    className={classNames(styles.status, {
      [styles.success]: theme === StatusBulletTheme.Success,
      [styles.neutral]: theme === StatusBulletTheme.Neutral,
    })}
  >
    {Icon ? <Icon className="w-4 h-4 text-success-foreground" /> : null}
    {value ? <span>{value}</span> : null}
  </div>
)
