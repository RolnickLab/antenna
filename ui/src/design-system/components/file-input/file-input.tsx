import { useRef } from 'react'
import { Button, ButtonTheme } from '../button/button'
import styles from './file-input.module.scss'
import { FileInputAccept } from './types'

const acceptValues: { [key in FileInputAccept]: string | undefined } = {
  [FileInputAccept.All]: undefined,
  [FileInputAccept.Images]: 'image/png, image/gif, image/jpeg',
}

interface FileInputProps {
  accept?: FileInputAccept
  label?: string
  loading?: boolean
  name: string
  onChange: (file: File | null) => void
}

export const FileInput = ({
  accept = FileInputAccept.All,
  label = 'Choose file',
  loading,
  name,
  onChange,
}: FileInputProps) => {
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div className={styles.container}>
      <input
        accept={acceptValues[accept]}
        className={styles.fileInput}
        disabled={loading}
        id={name}
        name={name}
        ref={inputRef}
        type="file"
        onChange={(e) => {
          const file = e.currentTarget.files?.[0]
          if (!file) {
            return
          }
          onChange(file)
        }}
      />
      <label htmlFor={name}>{!loading ? label : `${label}...`}</label>
      <Button
        label="Clear"
        theme={ButtonTheme.Plain}
        onClick={() => {
          if (inputRef.current) {
            inputRef.current.value = ''
            inputRef.current.files = null
          }
          onChange(null)
        }}
      />
    </div>
  )
}
