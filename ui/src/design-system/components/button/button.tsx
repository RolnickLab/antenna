import classNames from 'classnames'
import { forwardRef, MouseEvent } from 'react'
import { Icon, IconTheme, IconType } from '../icon/icon'
import styles from './button.module.scss'

export enum ButtonTheme {
  Default = 'default',
  Success = 'success',
  Plain = 'plain',
  Neutral = 'neutral',
  Destructive = 'destructive',
  Error = 'error',
}

interface ButtonProps {
  disabled?: boolean
  icon?: IconType
  label: string
  loading?: boolean
  theme?: ButtonTheme
  type?: 'submit' | 'button'
  onClick?: (e: MouseEvent) => void
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ ...props }, forwardedRef) => {
    const {
      disabled,
      icon,
      label,
      loading,
      theme = ButtonTheme.Default,
      type = 'button',
      onClick,
      ...rest
    } = props

    const iconTheme = (() => {
      switch (theme) {
        case ButtonTheme.Success:
        case ButtonTheme.Neutral:
        case ButtonTheme.Destructive:
          return IconTheme.Light
        case ButtonTheme.Error:
          return IconTheme.Error
        default:
          return IconTheme.Primary
      }
    })()

    return (
      <button
        ref={forwardedRef}
        className={classNames(styles.button, {
          [styles.success]: theme === ButtonTheme.Success,
          [styles.plain]: theme === ButtonTheme.Plain,
          [styles.neutral]: theme === ButtonTheme.Neutral,
          [styles.destructive]: theme === ButtonTheme.Destructive,
          [styles.error]: theme === ButtonTheme.Error,
          [styles.disabled]: disabled,
        })}
        disabled={disabled}
        type={type}
        onClick={(e) => {
          if (loading) {
            return
          }
          onClick?.(e)
        }}
        {...rest}
      >
        {icon && <Icon type={icon} theme={iconTheme} size={14} />}
        <span>{!loading ? label : `${label}...`}</span>
      </button>
    )
  }
)
