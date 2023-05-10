import classNames from 'classnames'
import _ from 'lodash'
import styles from './input.module.scss'

interface InputProps {
  name: string
  label: string
  placeholder?: string
  description?: string
}

export const Input = ({
  name,
  label,
  placeholder,
  description,
  type,
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
      />
      <span className={styles.description} id={hintName}>
        {description}
      </span>
    </div>
  )
}

export const PathInput = ({
  name,
  label,
  placeholder,
  description,
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
