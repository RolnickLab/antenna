import { DeleteForm } from 'components/form/delete-form/delete-form'
import { FormSection } from 'components/form/layout/layout'
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
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { ReactNode, useEffect, useState } from 'react'
import { bytesToMB } from 'utils/bytesToMB'
import { API_MAX_UPLOAD_SIZE } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import styles from './section-example-captures.module.scss'
import { useCaptureError } from './useCaptureError'

export const CAPTURE_CONFIG = {
  MAX_SIZE: API_MAX_UPLOAD_SIZE,
  NUM_CAPTURES: 20,
  RATIO: 16 / 9,
}

const CAPTURE_FIELD_DESCRIPTION = [
  translate(STRING.MESSAGE_CAPTURE_LIMIT, {
    numCaptures: CAPTURE_CONFIG.NUM_CAPTURES,
  }),
  translate(STRING.MESSAGE_IMAGE_SIZE, {
    value: bytesToMB(CAPTURE_CONFIG.MAX_SIZE),
    unit: 'MB',
  }),
  translate(STRING.MESSAGE_IMAGE_FORMAT),
  translate(STRING.MESSAGE_CAPTURE_FILENAME),
].join('\n')

export const SectionExampleCaptures = ({
  deployment,
}: {
  deployment: DeploymentDetails
}) => {
  const [files, setFiles] = useState<File[]>([])

  if (!deployment.createdAt) {
    return (
      <FormSection
        title={translate(STRING.FIELD_LABEL_UPLOADED_CAPTURES)}
        description={translate(STRING.MESSAGE_CAPTURE_UPLOAD_HIDDEN)}
      />
    )
  }

  const canUpload =
    deployment.exampleCaptures.length + files.length <
    CAPTURE_CONFIG.NUM_CAPTURES

  return (
    <FormSection
      title={translate(STRING.FIELD_LABEL_UPLOADED_CAPTURES)}
      description={CAPTURE_FIELD_DESCRIPTION}
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

        {canUpload && (
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
                  label={translate(STRING.RETRY)}
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
            type={translate(STRING.ENTITY_TYPE_CAPTURE)}
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
