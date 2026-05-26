import { FormSection } from 'components/form/layout/layout'
import { Button, buttonVariants, FileInput } from 'design-system'
import { PlusIcon, XIcon } from 'lucide-react'
import { ReactNode } from 'react'
import { API_MAX_UPLOAD_SIZE } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { bytesToMB } from 'utils/numberFormats'
import styles from './styles.module.scss'

const CAPTURE_CONFIG = {
  MAX_SIZE: API_MAX_UPLOAD_SIZE,
  NUM_CAPTURES: 20,
  RATIO: 16 / 9,
}

const TITLE = 'Select captures'

const DESCRIPTION = [
  translate(STRING.MESSAGE_CAPTURE_LIMIT, {
    numCaptures: CAPTURE_CONFIG.NUM_CAPTURES,
  }),
  translate(STRING.MESSAGE_IMAGE_SIZE, {
    value: bytesToMB(CAPTURE_CONFIG.MAX_SIZE),
    unit: 'MB',
  }),
  translate(STRING.MESSAGE_IMAGE_FORMAT),
].join('\n')

export const SelectImagesSection = ({
  images,
  setImages,
}: {
  images: { file: File }[]
  setImages: (images: { file: File }[]) => void
}) => {
  const canUpload = images.length < CAPTURE_CONFIG.NUM_CAPTURES

  return (
    <FormSection title={TITLE} description={DESCRIPTION}>
      <div className={styles.captures}>
        {images.map(({ file }) => (
          <Card key={file.name}>
            <div className={styles.cardContent}>
              <img src={URL.createObjectURL(file)} />
            </div>
            <div className={styles.cancelContainer}>
              <Button
                aria-label={translate(STRING.CLEAR)}
                onClick={() =>
                  setImages(
                    images.filter((image) => image.file.name !== file.name)
                  )
                }
                size="icon"
                variant="outline"
              >
                <XIcon className="w-4 h-4" />
              </Button>
            </div>
          </Card>
        ))}

        {canUpload && (
          <Card>
            <FileInput
              accept="images"
              multiple
              name="select-captures"
              renderInput={({ onClick }) => (
                <button
                  aria-label={translate(STRING.ADD)}
                  className="w-full h-full"
                  onClick={onClick}
                  type="button"
                >
                  <div
                    className={buttonVariants({
                      size: 'icon',
                      variant: 'success',
                    })}
                  >
                    <PlusIcon className="w-4 h-4" />
                  </div>
                </button>
              )}
              onChange={(files) => {
                if (!files) {
                  return
                }

                setImages([
                  ...images,
                  ...Array.from(files).map((file) => ({
                    file,
                  })),
                ])
              }}
            />
          </Card>
        )}
      </div>
    </FormSection>
  )
}

const Card = ({ children }: { children: ReactNode }) => (
  <div
    className={styles.card}
    style={{
      paddingBottom: `${(1 / CAPTURE_CONFIG.RATIO) * 100}%`,
    }}
  >
    <div className={styles.cardContent}>{children}</div>
  </div>
)
