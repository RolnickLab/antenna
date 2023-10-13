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
  Plain = 'plain',
  Primary = 'primary',
  Success = 'success',
  Error = 'error',
}

interface IconButtonProps {
  disabled?: boolean
  icon: IconType
  shape?: IconButtonShape
  theme?: IconButtonTheme
  title?: string
  onClick?: () => void
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ ...props }, forwardedRef) => {
    const {
      disabled,
      icon,
      shape = IconButtonShape.Square,
      theme = IconButtonTheme.Default,
      title,
      onClick,
      ...rest
    } = props

    const iconTheme = (() => {
      switch (theme) {
        case IconButtonTheme.Default:
          return IconTheme.Primary
        case IconButtonTheme.Plain:
          return IconTheme.Dark
        case IconButtonTheme.Error:
          return IconTheme.Error
        default:
          return IconTheme.Light
      }
    })()

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
          [styles.plain]: theme === IconButtonTheme.Plain,
          [styles.primary]: theme === IconButtonTheme.Primary,
          [styles.success]: theme === IconButtonTheme.Success,
          [styles.error]: theme === IconButtonTheme.Error,

          // Other
          [styles.disabled]: disabled,
        })}
        disabled={disabled}
        onClick={onClick}
        title={title}
        type="button"
        {...rest}
      >
        <Icon type={icon} theme={iconTheme} size={14} />
      </button>
    )
  }
)
