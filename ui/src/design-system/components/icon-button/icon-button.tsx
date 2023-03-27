import classNames from 'classnames'
import React from 'react'
import { Icon, IconTheme, IconType } from '../icon/icon'
import styles from './icon-button.module.scss'

export enum IconButtonShape {
  Square = 'square',
  Round = 'round',
}

export enum IconButtonTheme {
  Default = 'default',
  Neutral = 'neutral',
  Success = 'success',
}

interface IconButtonProps {
  icon: IconType
  shape?: IconButtonShape
  theme?: IconButtonTheme
  disabled?: boolean
  onClick?: () => void
}

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ ...props }, forwardedRef) => {
    const {
      icon,
      shape = IconButtonShape.Square,
      theme = IconButtonTheme.Default,
      disabled,
      onClick,
      ...rest
    } = props

    const iconTheme =
      theme === IconButtonTheme.Default ? IconTheme.Primary : IconTheme.Light

    return (
      <button
        ref={forwardedRef}
        className={classNames(styles.iconButton, {
          [styles.round]: shape === IconButtonShape.Round,
          [styles.square]: shape === IconButtonShape.Square,
          [styles.neutral]: theme === IconButtonTheme.Neutral,
          [styles.success]: theme === IconButtonTheme.Success,
          [styles.disabled]: disabled,
        })}
        disabled={disabled}
        onClick={onClick}
        {...rest}
      >
        <Icon type={icon} theme={iconTheme} size={10} />
      </button>
    )
  }
)
