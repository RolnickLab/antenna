import classNames from 'classnames'
import { FileInput } from 'design-system/components/file-input/file-input'
import { FileInputAccept } from 'design-system/components/file-input/types'
import { Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const ImageUpload = ({
  currentImage,
  file,
  name,
  onChange,
}: {
  currentImage?: string
  file?: File | null
  name: string
  onChange: (file: File | null) => void
}) => {
  const imageUrl = (() => {
    if (file) {
      return URL.createObjectURL(file)
    }
    if (file === null) {
      return undefined
    }
    return currentImage
  })()

  return (
    <>
      <div
        className={classNames(
          'flex items-center justify-center bg-primary-50',
          { 'aspect-video': !imageUrl }
        )}
      >
        {imageUrl ? (
          <img src={imageUrl} />
        ) : (
          <span className="body-small text-muted-foreground">
            {translate(STRING.MESSAGE_NO_IMAGE)}
          </span>
        )}
      </div>
      <FileInput
        accept={FileInputAccept.Images}
        name={name}
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
