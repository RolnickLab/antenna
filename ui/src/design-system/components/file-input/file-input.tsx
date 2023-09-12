import { ChangeEvent } from 'react'
import styles from './file-input.module.scss'

interface FileInputProps {
  label?: string
  loading?: boolean
  name: string
  onChange?: (e: ChangeEvent<HTMLInputElement>) => void
}

export const FileInput = ({
  label = 'Choose file',
  loading,
  name,
  onChange,
}: FileInputProps) => {
  return (
    <div>
      <input
        className={styles.fileInput}
        disabled={loading}
        id={name}
        name={name}
        type="file"
        onChange={onChange}
      />
      <label htmlFor={name}>{!loading ? label : `${label}...`}</label>
    </div>
  )
}
