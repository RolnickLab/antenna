import classNames from 'classnames'
import { FileInput } from 'design-system/components/file-input/file-input'
import { useState } from 'react'
import { UserInfo } from 'utils/user/types'
import styles from './user-info-image-upload.module.scss'

export const UserInfoImageUpload = ({
  userInfo,
  onChange,
}: {
  userInfo: UserInfo
  onChange: (image: File) => void
}) => {
  const [uploadedImageUrl, setUploadedImageUrl] = useState<string>()
  const imageUrl = uploadedImageUrl ?? userInfo.image

  return (
    <div className={styles.container}>
      <div className={styles.content}>
        {imageUrl ? <img src={imageUrl} /> : null}
        <div
          className={classNames(styles.overlay, {
            [styles.hasImage]: !!imageUrl,
          })}
        >
          <FileInput
            name="user-image"
            onChange={(e) => {
              const file = e.currentTarget.files?.[0]
              if (!file) {
                return
              }
              setUploadedImageUrl(URL.createObjectURL(file))
              onChange(file)
            }}
          />
        </div>
      </div>
    </div>
  )
}
