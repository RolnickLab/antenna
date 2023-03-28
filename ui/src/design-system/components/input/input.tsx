import classNames from 'classnames'
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
