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
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { InputContent } from 'design-system/components/input/input'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { ReactNode, useEffect, useState } from 'react'
import { bytesToMB } from 'utils/bytesToMB'
import { STRING, translate } from 'utils/language'
import styles from './section-example-captures.module.scss'
import { useCaptureError } from './useCaptureError'

export const CAPTURE_CONFIG = {
  MAX_SIZE: 1024 * 1024 * 10, // 10MB
  NUM_CAPTURES: 20,
  RATIO: 16 / 9,
}

// TODO: Move to translations when we are happy with the copy
export const COPY = {
  CAPTURE: 'capture',
  DESCRIPTIONS: [
    `A maximum of ${CAPTURE_CONFIG.NUM_CAPTURES} captures can be uploaded.`,
    `The image must smaller than ${bytesToMB(CAPTURE_CONFIG.MAX_SIZE)} MB.`,
    'Valid formats are PNG, GIF and JPEG.',
    'Image filenames must contain a timestamp in the format YYYYMMDDHHMMSS (e.g. 20210101120000-snapshot.jpg).',
  ],
  FIELD_LABEL_UPLOADED_CAPTURES: 'Manually uploaded captures',
  MESSAGE_CAPTURE_UPLOAD_HIDDEN:
    'Deployment must be saved before uploading captures.',
  MESSAGE_CAPTURE_LIMIT: `To upload more than ${CAPTURE_CONFIG.NUM_CAPTURES} images you must configure a data source.`,
  RETRY: 'Retry',
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
        label={COPY.FIELD_LABEL_UPLOADED_CAPTURES}
        description={COPY.MESSAGE_CAPTURE_UPLOAD_HIDDEN}
      />
    )
  }

  return (
    <InputContent
      label={COPY.FIELD_LABEL_UPLOADED_CAPTURES}
      description={COPY.DESCRIPTIONS.join('\n')}
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
            index={deployment.exampleCaptures.length + index}
            onUploaded={() => setFiles(files.filter((f) => f !== file))}
          />
        ))}

        {deployment.exampleCaptures.length <= CAPTURE_CONFIG.NUM_CAPTURES ? (
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
      paddingBottom: `${(1 / CAPTURE_CONFIG.RATIO) * 100}%`,
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
  index,
  file,
  onUploaded,
}: {
  deploymentId: string
  file: File
  index: number
  onUploaded: () => void
}) => {
  const { uploadCapture, isLoading, isSuccess, error } =
    useUploadCapture(onUploaded)

  const { isValid, errorMessage, allowRetry } = useCaptureError({
    error,
    file,
    index,
  })

  useEffect(() => {
    if (!isValid || isSuccess) {
      return
    }

    uploadCapture({ deploymentId, file })
  }, [])

  if (isSuccess) {
    return null
  }

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
              {allowRetry ? (
                <Button
                  icon={IconType.Error}
                  label={COPY.RETRY}
                  theme={ButtonTheme.Error}
                  onClick={() => {
                    uploadCapture({ deploymentId, file })
                  }}
                />
              ) : (
                <div className={styles.iconWrapper}>
                  <Icon type={IconType.Error} theme={IconTheme.Error} />
                </div>
              )}
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
            type={COPY.CAPTURE}
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
