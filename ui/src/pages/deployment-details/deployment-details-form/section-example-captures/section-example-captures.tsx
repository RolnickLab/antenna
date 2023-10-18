import { DeleteForm } from 'components/form/delete-form/delete-form'
import { useDeleteCapture } from 'data-services/hooks/captures/useDeleteCapture'
import { useUploadCapture } from 'data-services/hooks/captures/useUploadCapture'
import { DeploymentDetails } from 'data-services/models/deployment-details'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { FileInput } from 'design-system/components/file-input/file-input'
import { FileInputAccept } from 'design-system/components/file-input/types'
import {
  IconButton,
  IconButtonShape,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { InputContent } from 'design-system/components/input/input'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { ReactNode, useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import styles from './section-example-captures.module.scss'

const IMAGE_CONFIG = {
  MAX_SIZE: 1024 * 1024, // 1MB
  NUM_IMAGES: 12,
  RATIO: 16 / 9,
}

export const SectionExampleCaptures = ({
  deployment,
}: {
  deployment: DeploymentDetails
}) => {
  const [files, setFiles] = useState<File[]>([])

  if (!deployment.createdAt) {
    return (
      <InputContent
        label={translate(STRING.FIELD_LABEL_UPLOADED_CAPTURES)}
        description="Deployment must be saved before uploading captures."
      />
    )
  }

  return (
    <InputContent
      label={translate(STRING.FIELD_LABEL_UPLOADED_CAPTURES)}
      description="Valid formats are PNG, GIF and JPEG. Image filenames must contain a timestamp in the format YYYYMMDDHHMMSS (e.g. 20210101120000-snapshot.jpg)."
    >
      <div className={styles.collection}>
        {deployment.exampleCaptures.map((exampelCapture) => (
          <ExampleCapture
            key={exampelCapture.id}
            id={exampelCapture.id}
            src={exampelCapture.src}
          />
        ))}

        {files.map((file, index) => (
          <AddedExampleCapture
            key={index}
            deploymentId={deployment.id}
            file={file}
            onUploaded={() => setFiles(files.filter((f) => f !== file))}
          />
        ))}

        {deployment.exampleCaptures.length <= IMAGE_CONFIG.MAX_SIZE ? (
          <Card>
            <FileInput
              accept={FileInputAccept.Images}
              multiple
              name="example-captures"
              renderInput={(props) => (
                <IconButton
                  {...props}
                  icon={IconType.Plus}
                  shape={IconButtonShape.Round}
                  theme={IconButtonTheme.Success}
                />
              )}
              onChange={(newFiles) =>
                setFiles([...files, ...Array.from(newFiles ?? [])])
              }
            />
          </Card>
        ) : null}
      </div>
    </InputContent>
  )
}

const Card = ({ children }: { children: ReactNode }) => (
  <div
    className={styles.card}
    style={{
      paddingBottom: `${(1 / IMAGE_CONFIG.RATIO) * 100}%`,
    }}
  >
    <div className={styles.cardContent}>{children}</div>
  </div>
)

const ExampleCapture = ({ id, src }: { id: string; src: string }) => (
  <Card>
    <div className={styles.cardContent}>
      <img src={src} />
    </div>
    <div className={styles.cardContent}>
      <div className={styles.deleteContainer}>
        <DeleteCaptureDialog id={id} />
      </div>
    </div>
  </Card>
)

const AddedExampleCapture = ({
  deploymentId,
  file,
  onUploaded,
}: {
  deploymentId: string
  file: File
  onUploaded: () => void
}) => {
  const { uploadCapture, isLoading, isSuccess, error } =
    useUploadCapture(onUploaded)

  useEffect(() => {
    if (!isSuccess) {
      uploadCapture({ deploymentId, file })
    }
  }, [])

  if (isSuccess) {
    return null
  }

  const errorMessage = (() => {
    if (!error) {
      return undefined
    }

    const { message, fieldErrors } = parseServerError(error)

    if (fieldErrors.length) {
      return fieldErrors.map(({ message }) => message).join('\n')
    }

    return message
  })()

  return (
    <Card>
      <div className={styles.cardContent}>
        <img src={URL.createObjectURL(file)} />
      </div>
      <div className={styles.cardContent}>
        {isLoading ? <LoadingSpinner size={32} /> : null}
        {errorMessage && (
          <>
            <Tooltip content={errorMessage}>
              <Button
                icon={IconType.Error}
                label="Retry"
                theme={ButtonTheme.Error}
                onClick={() => uploadCapture({ deploymentId, file })}
              />
            </Tooltip>
            <div className={styles.cancelContainer}>
              <IconButton
                icon={IconType.Cross}
                shape={IconButtonShape.Round}
                onClick={onUploaded}
              />
            </div>
          </>
        )}
      </div>
    </Card>
  )
}

const DeleteCaptureDialog = ({ id }: { id: string }) => {
  const [isOpen, setIsOpen] = useState(false)
  const { deleteCapture, isLoading, error, isSuccess } = useDeleteCapture()

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <IconButton icon={IconType.RadixTrash} />
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        <div className={styles.deleteDialog}>
          <DeleteForm
            error={error}
            type="capture"
            isLoading={isLoading}
            isSuccess={isSuccess}
            onCancel={() => setIsOpen(false)}
            onSubmit={() => deleteCapture(id)}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
