import classNames from 'classnames'
import { useState } from 'react'
import styles from './input.module.scss'

interface InputProps {
  name: string
  label: string
  placeholder?: string
  description?: string
  type?: 'text' | 'number' | 'file'
}

export const Input = (props: InputProps) => {
  switch (props.type) {
    case 'file':
      return <FileInput {...props} />
    default:
      return <ValueInput {...props} />
  }
}

const ValueInput = ({
  name,
  label,
  placeholder,
  description,
  type,
}: InputProps) => {
  const hintName = `hint-${name}`

  return (
    <>
      <label className={styles.label} htmlFor={name}>
        {label}
      </label>
      <input
        className={styles.valueInput}
        id={name}
        type={type}
        aria-describedby={hintName}
        placeholder={placeholder}
      />
      <span id={hintName} className={styles.description}>
        {description}
      </span>
    </>
  )
}

const FileInput = ({ name, label, placeholder, description }: InputProps) => {
  const [value, setValue] = useState<string>()
  const hintName = `hint-${name}`

  return (
    <>
      <label className={styles.label} htmlFor={name}>
        {label}
      </label>
      <label className={styles.fileInputWrapper}>
        <input
          id={name}
          type="file"
          onChange={(e) => setValue(e.currentTarget.value)}
        />
        <span
          data-content={value ?? placeholder}
          className={classNames(styles.customInput, {
            [styles.placeholder]: !value,
          })}
          aria-hidden="true"
        />
      </label>
      <span id={hintName} className={styles.description}>
        {description}
      </span>
    </>
  )
}
