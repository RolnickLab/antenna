import { useDeleteCapture } from 'data-services/hooks/captures/useDeleteCapture'
import { useUploadCapture } from 'data-services/hooks/captures/useUploadCapture'
import { DeploymentDetails } from 'data-services/models/deployment-details'
import { Button, ButtonTheme } from 'design-system/components/button/button'
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

  return (
    <InputContent
      label={translate(STRING.FIELD_LABEL_EXAMPLE_CAPTURES)}
      description="Valid formats are PNG, GIF and JPEG."
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

const ExampleCapture = ({ id, src }: { id: string; src: string }) => {
  const { deleteCapture, isLoading, error, isSuccess } = useDeleteCapture()

  if (isSuccess) {
    return null
  }

  return (
    <Card>
      <div className={styles.cardContent}>
        <img src={src} />
      </div>
      <div className={styles.cardContent}>
        {isLoading ? (
          <LoadingSpinner size={32} />
        ) : (
          <div className={styles.deleteContainer}>
            <IconButton
              icon={IconType.Cross}
              shape={IconButtonShape.Round}
              onClick={() => deleteCapture(id)}
            />
          </div>
        )}
        {!!error && (
          <ErrorMessage
            error={error}
            label="Retry delete"
            onClick={() => deleteCapture(id)}
          />
        )}
      </div>
    </Card>
  )
}

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
        {!!error && (
          <>
            <ErrorMessage
              error={error}
              label="Retry upload"
              onClick={() => uploadCapture({ deploymentId, file })}
            />
            <div className={styles.deleteContainer}>
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

const ErrorMessage = ({
  error,
  label,
  onClick,
}: {
  error: unknown
  label: string
  onClick: () => void
}) => {
  const errorMessage = (() => {
    const { message, fieldErrors } = parseServerError(error)

    if (fieldErrors.length) {
      return fieldErrors.map((e) => e.message).join('\n')
    }

    return message
  })()

  return (
    <Tooltip content={errorMessage}>
      <Button
        icon={IconType.Error}
        label={label}
        theme={ButtonTheme.Error}
        onClick={onClick}
      />
    </Tooltip>
  )
}
