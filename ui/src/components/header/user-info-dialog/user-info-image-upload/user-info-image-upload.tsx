import classNames from 'classnames'
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
    <div className={styles.container}>
      <div className={styles.content}>
        {imageUrl ? <img src={imageUrl} /> : null}
        <div
          className={classNames(styles.overlay, {
            [styles.hasImage]: !!imageUrl,
          })}
        >
          <FileInput
            accept={FileInputAccept.Images}
            label="Choose image"
            name="user-image"
            onChange={onChange}
          />
        </div>
      </div>
    </div>
  )
}
