import { Button } from 'design-system'
import { useRef } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './file-input.module.scss'

const acceptValues: { [key: string]: string | undefined } = {
  all: undefined,
  images: 'image/png, image/gif, image/jpeg',
}

interface FileInputProps {
  accept?: 'all' | 'images'
  loading?: boolean
  multiple?: boolean
  name: string
  renderInput: (props: {
    loading?: boolean
    onClick: () => void
  }) => JSX.Element
  withClear?: boolean
  onChange: (files: FileList | null) => void
}

export const FileInput = ({
  accept = 'all',
  loading,
  multiple,
  name,
  renderInput,
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
        tabIndex={-1}
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
      {renderInput({ loading, onClick: () => inputRef.current?.click() })}
      {withClear && (
        <Button
          onClick={() => {
            if (inputRef.current) {
              inputRef.current.value = ''
              inputRef.current.files = null
            }
            onChange(null)
          }}
          size="small"
          type="button"
          variant="ghost"
        >
          <span>{translate(STRING.CLEAR)}</span>
        </Button>
      )}
    </div>
  )
}
