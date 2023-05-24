import classNames from 'classnames'
import { forwardRef } from 'react'
import { Icon, IconTheme, IconType } from '../icon/icon'
import styles from './button.module.scss'

export enum ButtonTheme {
  Default = 'default',
  Success = 'success',
  Plain = 'plain',
}

interface ButtonProps {
  disabled?: boolean
  icon?: IconType
  label: string
  theme?: ButtonTheme
  type?: 'submit' | 'button'
  onClick?: () => void
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ ...props }, forwardedRef) => {
    const {
      disabled,
      icon,
      label,
      theme = ButtonTheme.Default,
      type = 'button',
      onClick,
      ...rest
    } = props

    const iconTheme =
      theme === ButtonTheme.Success ? IconTheme.Light : IconTheme.Primary

    return (
      <button
        ref={forwardedRef}
        className={classNames(styles.button, {
          [styles.success]: theme === ButtonTheme.Success,
          [styles.plain]: theme === ButtonTheme.Plain,
          [styles.disabled]: disabled,
        })}
        disabled={disabled}
        type={type}
        onClick={onClick}
        {...rest}
      >
        {icon && <Icon type={icon} theme={iconTheme} size={16} />}
        <span>{label}</span>
      </button>
    )
  }
)
