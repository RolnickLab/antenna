import _ from 'lodash'
import { ChangeEvent, FocusEvent, forwardRef } from 'react'
import styles from './input.module.scss'

interface InputProps {
  description?: string
  error?: string
  label: string
  name: string
  placeholder?: string
  value?: string | number
  type?: 'text' | 'number'
  onBlur?: (e: FocusEvent<HTMLInputElement>) => void
  onChange?: (e: ChangeEvent<HTMLInputElement>) => void
  onFocus?: (e: FocusEvent<HTMLInputElement>) => void
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ ...props }, forwardedRef) => {
    const { description, error, label, name, ...rest } = props

    const hasDescription = !!description?.length
    const descriptionId = hasDescription ? `description-${name}` : undefined

    const hasError = !!error?.length
    const errorId = error ? `error-${name}` : undefined

    return (
      <div className={styles.container}>
        <div className={styles.line}>
          <label className={styles.label} htmlFor={name}>
            {label}
          </label>
          {hasError ? <span className={styles.error}>{error}</span> : undefined}
        </div>
        <input
          aria-describedby={descriptionId}
          aria-errormessage={errorId}
          aria-invalid={hasError}
          className={styles.input}
          id={name}
          name={name}
          ref={forwardedRef}
          {...rest}
        />
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
  const value = _.isNumber(_value) ? _value.toLocaleString() : _value

  return (
    <div>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>{value?.length ? value : '-'}</span>
    </div>
  )
}
