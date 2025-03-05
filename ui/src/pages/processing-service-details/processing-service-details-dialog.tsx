import { ErrorState } from 'components/error-state/error-state'
import { FormRow, FormSection } from 'components/form/layout/layout'
import { useProcessingServiceDetails } from 'data-services/hooks/processing-services/useProcessingServiceDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputValue } from 'design-system/components/input/input'
import _ from 'lodash'
import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { ProcessingServicePipelines } from './processing-service-pipelines'
import styles from './styles.module.scss'

export const ProcessingServiceDetailsDialog = ({
  id,
  projectId,
  name,
}: {
  id: string
  projectId: string
  name: string
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <button className={styles.dialogTrigger}>
          <span>{name}</span>
        </button>
      </Dialog.Trigger>
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
      >
        <Dialog.Header
          title={translate(STRING.ENTITY_DETAILS, {
            type: _.capitalize(
              translate(STRING.ENTITY_TYPE_PROCESSING_SERVICE)
            ),
          })}
        />
        <div className={styles.content}>
          <ProcessingServiceDetailsContent
            id={id}
            projectId={projectId}
            onLoadingChange={setIsLoading}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const ProcessingServiceDetailsContent = ({
  id,
  projectId,
  onLoadingChange,
}: {
  id: string
  projectId: string
  onLoadingChange: (isLoading: boolean) => void
}) => {
  const { processingService, isLoading, error } = useProcessingServiceDetails(
    id,
    { projectId }
  )

  useEffect(() => {
    onLoadingChange(isLoading)
  }, [isLoading])

  return (
    <>
      {processingService ? (
        <>
          <FormSection title={translate(STRING.SUMMARY)}>
            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_ID)}
                value={processingService.id}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_NAME)}
                value={processingService.name}
              />
            </FormRow>
            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_DESCRIPTION)}
                value={processingService.description}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_LAST_CHECKED)}
                value={processingService.lastChecked}
              />
            </FormRow>

            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_CREATED_AT)}
                value={processingService.createdAt}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_UPDATED_AT)}
                value={processingService.updatedAt}
              />
            </FormRow>
          </FormSection>
          {processingService.pipelines.length > 0 && (
            <FormSection title={translate(STRING.PIPELINES)}>
              <div className={styles.tableContainer}>
                <ProcessingServicePipelines
                  processingService={processingService}
                />
              </div>
            </FormSection>
          )}
        </>
      ) : error ? (
        <div className={styles.errorContent}>
          <ErrorState error={error} />
        </div>
      ) : null}
    </>
  )
}
