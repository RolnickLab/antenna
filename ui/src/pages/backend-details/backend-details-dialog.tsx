import { FormRow, FormSection } from 'components/form/layout/layout'
import { useBackendDetails } from 'data-services/hooks/backends/useBackendDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputValue } from 'design-system/components/input/input'
import _ from 'lodash'
import { Error } from 'pages/error/error'
import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { BackendPipelines } from './backend-pipelines'
import styles from './styles.module.scss'

export const BackendDetailsDialog = ({
  id,
  name,
}: {
  id: string
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
            type: _.capitalize(translate(STRING.ENTITY_TYPE_BACKEND)),
          })}
        />
        <div className={styles.content}>
          <BackendDetailsContent id={id} onLoadingChange={setIsLoading} />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const BackendDetailsContent = ({
  id,
  onLoadingChange,
}: {
  id: string
  onLoadingChange: (isLoading: boolean) => void
}) => {
  const { backend, isLoading, error } = useBackendDetails(id)

  useEffect(() => {
    onLoadingChange(isLoading)
  }, [isLoading])

  return (
    <>
      {backend ? (
        <>
          <FormSection title={translate(STRING.SUMMARY)}>
            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_ID)}
                value={backend.id}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_VERSION)}
                value={backend.versionLabel}
              />
            </FormRow>
            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_NAME)}
                value={backend.name}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_DESCRIPTION)}
                value={backend.description}
              />
            </FormRow>

            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_CREATED_AT)}
                value={backend.createdAt}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_UPDATED_AT)}
                value={backend.updatedAt}
              />
            </FormRow>
          </FormSection>
          {backend.pipelines.length > 0 && (
            <FormSection title={translate(STRING.PIPELINES)}>
              <div className={styles.tableContainer}>
                <BackendPipelines backend={backend} />
              </div>
            </FormSection>
          )}
        </>
      ) : error ? (
        <div className={styles.errorContent}>
          <Error error={error} />
        </div>
      ) : null}
    </>
  )
}
