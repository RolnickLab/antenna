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
  multiple?: boolean
  name: string
  withClear?: boolean
  onChange: (files: FileList | null) => void
}

export const FileInput = ({
  accept = FileInputAccept.All,
  label = 'Choose file',
  loading,
  multiple,
  name,
  withClear,
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
        multiple={multiple}
        name={name}
        ref={inputRef}
        type="file"
        onChange={(e) => {
          const files = e.currentTarget.files
          if (!files?.length) {
            return
          }
          onChange(files)
          e.currentTarget.value = ''
        }}
      />
      <label htmlFor={name}>{!loading ? label : `${label}...`}</label>
      {withClear && (
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
      )}
    </div>
  )
}
