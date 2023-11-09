import classNames from 'classnames'
import _ from 'lodash'
import {
  ChangeEvent,
  CSSProperties,
  FocusEvent,
  forwardRef,
  ReactNode,
  useState,
} from 'react'
import { Link } from 'react-router-dom'
import { IconButton, IconButtonTheme } from '../icon-button/icon-button'
import { IconType } from '../icon/icon'
import { Tooltip } from '../tooltip/tooltip'
import styles from './input.module.scss'

interface InputProps {
  description?: string
  disabled?: boolean
  error?: string
  label: string
  name: string
  placeholder?: string
  value?: string | number
  type?: 'text' | 'number' | 'password'
  onBlur?: (e: FocusEvent<HTMLInputElement>) => void
  onChange?: (e: ChangeEvent<HTMLInputElement>) => void
  onFocus?: (e: FocusEvent<HTMLInputElement>) => void
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ ...props }, forwardedRef) => {
    const {
      description,
      disabled,
      error,
      label,
      name,
      type: initialType,
      ...rest
    } = props
    const [type, setType] = useState(initialType)

    const hasDescription = !!description?.length
    const descriptionId = hasDescription ? `description-${name}` : undefined

    const hasError = !!error?.length
    const errorId = error ? `error-${name}` : undefined

    return (
      <div className={styles.container}>
        <div className={styles.labelRow}>
          <label className={styles.label} htmlFor={name}>
            {label}
          </label>
          {hasError ? (
            <span id={errorId} className={styles.error}>
              {error}
            </span>
          ) : undefined}
        </div>
        <div className={styles.inputContainer}>
          <input
            aria-disabled={disabled}
            aria-describedby={descriptionId}
            aria-errormessage={errorId}
            aria-invalid={hasError}
            autoComplete="on"
            className={classNames(styles.input, {
              [styles.password]: initialType === 'password',
            })}
            disabled={disabled}
            id={name}
            name={name}
            ref={forwardedRef}
            step={type === 'number' ? 'any' : undefined}
            type={type}
            {...rest}
          />
          {initialType === 'password' ? (
            <div className={styles.passwordButtonContainer}>
              <Tooltip
                content={`${type === 'password' ? 'Show' : 'Hide'} password`}
              >
                <IconButton
                  icon={IconType.BatchId}
                  theme={IconButtonTheme.Plain}
                  onClick={() =>
                    setType(type === 'password' ? 'text' : 'password')
                  }
                />
              </Tooltip>
            </div>
          ) : null}
        </div>
        {hasDescription ? (
          <span id={descriptionId} className={styles.description}>
            {description}
          </span>
        ) : undefined}
      </div>
    )
  }
)

export const InputValue = ({
  label,
  value: _value,
  to,
}: {
  label: string
  value?: string | number
  to?: string
}) => {
  const value =
    _value === undefined
      ? 'N/A'
      : _.isNumber(_value)
      ? _value.toLocaleString()
      : _value

  return (
    <InputContent label={label}>
      {to ? (
        <Link to={to} className={classNames(styles.value, styles.link)}>
          {value}
        </Link>
      ) : (
        <span className={styles.value}>{value}</span>
      )}
    </InputContent>
  )
}

export const InputContent = ({
  description,
  error,
  label,
  style,
  children,
}: {
  description?: string
  error?: string
  label: string
  style?: CSSProperties
  children?: ReactNode
}) => {
  const hasError = !!error?.length
  const hasDescription = !!description?.length

  return (
    <div className={styles.container} style={style}>
      <div className={styles.labelRow}>
        <span className={styles.label}>{label}</span>
        {hasError ? <span className={styles.error}>{error}</span> : undefined}
      </div>
      <div className={styles.content}>{children}</div>
      {hasDescription ? (
        <span className={styles.description}>{description}</span>
      ) : undefined}
    </div>
  )
}
