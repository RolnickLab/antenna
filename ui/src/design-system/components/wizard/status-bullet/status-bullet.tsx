import classNames from 'classnames'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import styles from './status-bullet.module.scss'

export enum StatusBulletTheme {
  Default = 'default',
  Success = 'success',
  Neutral = 'neutral',
}

interface StatusBulletProps {
  icon?: IconType
  value?: number
  theme?: StatusBulletTheme
}

export const StatusBullet = ({
  icon,
  theme = StatusBulletTheme.Default,
  value,
}: StatusBulletProps) => (
  <div
    className={classNames(styles.status, {
      [styles.success]: theme === StatusBulletTheme.Success,
      [styles.neutral]: theme === StatusBulletTheme.Neutral,
    })}
  >
    {icon ? <Icon type={icon} theme={IconTheme.Light} /> : null}
    {value ? <span>{value}</span> : null}
  </div>
)
