import classNames from 'classnames'
import _ from 'lodash'
import { ChangeEvent, FocusEvent, forwardRef, ReactNode, useState } from 'react'
import { IconButton, IconButtonTheme } from '../icon-button/icon-button'
import { IconType } from '../icon/icon'
import { Tooltip } from '../tooltip/tooltip'
import styles from './input.module.scss'

interface InputProps {
  description?: string
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
          {hasError ? <span className={styles.error}>{error}</span> : undefined}
        </div>
        <div className={styles.inputContainer}>
          <input
            aria-describedby={descriptionId}
            aria-errormessage={errorId}
            aria-invalid={hasError}
            autoComplete="on"
            className={classNames(styles.input, {
              [styles.password]: initialType === 'password',
            })}
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
          <span className={styles.description} id={descriptionId}>
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
}: {
  label: string
  value?: string | number
}) => {
  const value =
    _value === undefined
      ? 'N/A'
      : _.isNumber(_value)
      ? _value.toLocaleString()
      : _value

  return (
    <InputContent label={label}>
      <span className={styles.value}>{value}</span>
    </InputContent>
  )
}

export const InputContent = ({
  label,
  children,
}: {
  label: string
  children?: ReactNode
}) => (
  <div className={styles.container}>
    <span className={styles.label}>{label}</span>
    <div className={styles.content}>{children}</div>
  </div>
)
