import classNames from 'classnames'
import _ from 'lodash'
import styles from './input.module.scss'

interface InputProps {
  description?: string
  label: string
  name: string

  placeholder?: string
  value?: string | number
  onBlur?: () => void
  onChange?: (value: string | number) => void
}

export const Input = ({
  description,
  label,
  name,
  placeholder,
  type,
  value,
  onBlur,
  onChange,
}: InputProps & { type?: 'text' | 'number' }) => {
  const hintName = `hint-${name}`

  return (
    <div>
      <label className={styles.label} htmlFor={name}>
        {label}
      </label>
      <input
        aria-describedby={hintName}
        className={styles.valueInput}
        id={name}
        placeholder={placeholder}
        type={type}
        value={value}
        onChange={(e) => onChange?.(e.currentTarget.value)}
        onBlur={() => onBlur?.()}
      />
      <span className={styles.description} id={hintName}>
        {description}
      </span>
    </div>
  )
}

export const PathInput = ({
  description,
  label,
  name,
  placeholder,
}: InputProps) => {
  const hintName = `hint-${name}`

  return (
    <div>
      <label className={styles.label} htmlFor={name}>
        {label}
      </label>
      <button
        aria-describedby={hintName}
        className={classNames(styles.pathInput, {
          [styles.placeholder]: true,
        })}
        data-content={placeholder}
        id={name}
        onClick={() => alert('Selecting a path is WIP.')}
      />
      <span className={styles.description} id={hintName}>
        {description}
      </span>
    </div>
  )
}

export const InputValue = ({
  label,
  value: _value,
}: {
  label: string
  value: string | number
}) => {
  const value = _.isNumber(_value) ? _value.toLocaleString() : _value

  return (
    <div>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>{value}</span>
    </div>
  )
}
