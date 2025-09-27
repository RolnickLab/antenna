import classNames from 'classnames'
import { FileInput } from 'design-system/components/file-input/file-input'
import { FileInputAccept } from 'design-system/components/file-input/types'
import { Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
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
      <div className={classNames('bg-primary-50', styles.container)}>
        <div className={styles.content}>
          {imageUrl ? (
            <>
              <img src={imageUrl} />
              <ImageOverlay />
            </>
          ) : (
            <span className="body-small text-muted-foreground">
              {translate(STRING.MESSAGE_NO_IMAGE)}
            </span>
          )}
        </div>
      </div>
      <FileInput
        accept={FileInputAccept.Images}
        name="user-image"
        renderInput={(props) => (
          <Button
            onClick={props.onClick}
            size="small"
            type="button"
            variant="outline"
          >
            <span>
              {imageUrl
                ? translate(STRING.CHANGE_IMAGE)
                : translate(STRING.CHOOSE_IMAGE)}
            </span>
            {props.loading ? (
              <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
            ) : null}
          </Button>
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
