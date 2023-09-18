import { FileInput } from 'design-system/components/file-input/file-input'
import { FileInputAccept } from 'design-system/components/file-input/types'
import { useState } from 'react'
import { UserInfo } from 'utils/user/types'
import styles from './user-info-image-upload.module.scss'

export const UserInfoImageUpload = ({
  file,
  userInfo,
  onChange,
}: {
  file?: File | null
  userInfo: UserInfo
  onChange: (file: File | null) => void
}) => {
  const [_size, setSize] = useState<{ width: number; height: number }>()
  const imageUrl = (() => {
    if (file) {
      return URL.createObjectURL(file)
    }
    if (file === null) {
      return undefined
    }
    return userInfo.image
  })()

  return (
    <>
      <div className={styles.container}>
        <div className={styles.content}>
          {imageUrl ? (
            <>
              <img
                src={imageUrl}
                onLoad={(e) => {
                  const width = e.currentTarget.naturalWidth
                  const height = e.currentTarget.naturalHeight
                  setSize({ width, height })
                }}
              />
              <ImageOverlay />
            </>
          ) : (
            <span>No image</span>
          )}
        </div>
      </div>
      <FileInput
        accept={FileInputAccept.Images}
        label="Choose image"
        name="user-image"
        onChange={onChange}
      />
    </>
  )
}

const ImageOverlay = () => (
  <svg className={styles.overlay}>
    <defs>
      <mask id="hole">
        <rect width="100%" height="100%" fill="white" />
        <circle cx="50%" cy="50%" r="50%" fill="black" />
      </mask>
    </defs>
    <rect
      fill="black"
      fillOpacity={0.7}
      width="100%"
      height="100%"
      mask="url(#hole)"
    />
  </svg>
)
