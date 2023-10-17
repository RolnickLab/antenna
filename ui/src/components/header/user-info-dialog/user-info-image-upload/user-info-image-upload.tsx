import { Button } from 'design-system/components/button/button'
import { FileInput } from 'design-system/components/file-input/file-input'
import { FileInputAccept } from 'design-system/components/file-input/types'
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
              <img src={imageUrl} />
              <ImageOverlay />
            </>
          ) : (
            <span>No image</span>
          )}
        </div>
      </div>
      <FileInput
        accept={FileInputAccept.Images}
        name="user-image"
        renderInput={(props) => (
          <Button
            {...props}
            label={imageUrl ? 'Change image' : 'Choose image'}
          />
        )}
        withClear
        onChange={(files) => onChange(files ? files[0] : null)}
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
      fillOpacity={0.4}
      width="100%"
      height="100%"
      mask="url(#hole)"
    />
    <circle
      cx="50%"
      cy="50%"
      r="50%"
      fill="transparent"
      stroke="white"
      strokeWidth="1px"
    />
  </svg>
)
