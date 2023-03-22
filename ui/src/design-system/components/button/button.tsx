import classNames from 'classnames'
import React from 'react'
import { Icon, IconTheme, IconType } from '../icon/icon'
import styles from './button.module.scss'

export enum ButtonTheme {
  Default = 'default',
  Success = 'success',
  Plain = 'plain',
}

interface ButtonProps {
  label: string
  icon?: IconType
  theme?: ButtonTheme
  onClick?: () => void
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ ...props }, forwardedRef) => {
    const { label, icon, theme = ButtonTheme.Default, onClick, ...rest } = props

    const iconTheme =
      theme === ButtonTheme.Success ? IconTheme.Light : IconTheme.Primary

    return (
      <button
        ref={forwardedRef}
        className={classNames(styles.button, {
          [styles.success]: theme === ButtonTheme.Success,
          [styles.plain]: theme === ButtonTheme.Plain,
        })}
        onClick={onClick}
        {...rest}
      >
        {icon && <Icon type={icon} theme={iconTheme} size={16} />}
        <span>{label}</span>
      </button>
    )
  }
)
