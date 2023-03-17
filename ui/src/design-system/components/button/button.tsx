import classNames from 'classnames'
import { Icon, IconTheme, IconType } from '../icon/icon'
import styles from './button.module.scss'

export enum ButtonTheme {
  Default = 'default',
  Success = 'success',
}

interface ButtonProps {
  label: string
  icon?: IconType
  theme?: ButtonTheme
  onClick: () => void
}

export const Button = ({
  label,
  icon,
  theme = ButtonTheme.Default,
  onClick,
}: ButtonProps) => {
  const iconTheme =
    theme === ButtonTheme.Success ? IconTheme.Light : IconTheme.Primary

  return (
    <button
      className={classNames(styles.button, {
        [styles.success]: theme === ButtonTheme.Success,
      })}
      onClick={onClick}
    >
      {icon && <Icon type={icon} theme={iconTheme} size={16} />}
      <span>{label}</span>
    </button>
  )
}
