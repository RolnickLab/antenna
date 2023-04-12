import classNames from 'classnames'
import { forwardRef } from 'react'
import { Icon, IconTheme, IconType } from '../icon/icon'
import styles from './icon-button.module.scss'

export enum IconButtonShape {
  Square = 'square',
  Round = 'round',
  RoundLarge = 'round-large',
}

export enum IconButtonTheme {
  Default = 'default',
  Neutral = 'neutral',
  Primary = 'primary',
  Success = 'success',
}

interface IconButtonProps {
  icon: IconType
  shape?: IconButtonShape
  theme?: IconButtonTheme
  disabled?: boolean
  onClick?: () => void
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
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
          // Shape
          [styles.square]: shape === IconButtonShape.Square,
          [styles.round]: shape === IconButtonShape.Round,
          [styles.roundLarge]: shape === IconButtonShape.RoundLarge,

          // Theme
          [styles.neutral]: theme === IconButtonTheme.Neutral,
          [styles.primary]: theme === IconButtonTheme.Primary,
          [styles.success]: theme === IconButtonTheme.Success,

          // Other
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
