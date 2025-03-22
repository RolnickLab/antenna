import { ErrorState } from 'components/error-state/error-state'
import { FormRow, FormSection } from 'components/form/layout/layout'
import { useAlgorithmDetails } from 'data-services/hooks/algorithm/useAlgorithmDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputValue } from 'design-system/components/input/input'
import _ from 'lodash'
import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './styles.module.scss'

export const AlgorithmDetailsDialog = ({
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
            type: _.capitalize(translate(STRING.ENTITY_TYPE_ALGORITHM)),
          })}
        />
        <div className={styles.content}>
          <AlgorithmDetailsContent id={id} onLoadingChange={setIsLoading} />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const AlgorithmDetailsContent = ({
  id,
  onLoadingChange,
}: {
  id: string
  onLoadingChange: (isLoading: boolean) => void
}) => {
  const { algorithm, isLoading, error } = useAlgorithmDetails(id)

  useEffect(() => {
    onLoadingChange(isLoading)
  }, [isLoading])

  return (
    <>
      {algorithm ? (
        <>
          <FormSection title={translate(STRING.SUMMARY)}>
            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_ID)}
                value={algorithm.id}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_NAME)}
                value={algorithm.name}
              />
            </FormRow>
            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_KEY)}
                value={algorithm.key}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_TASK_TYPE)}
                value={algorithm.taskType}
              />
            </FormRow>

            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_CREATED_AT)}
                value={algorithm.createdAt}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_UPDATED_AT)}
                value={algorithm.updatedAt}
              />
            </FormRow>
            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_URI)}
                value={algorithm.uri}
                to={algorithm.uri}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_CATEGORY_MAP_ID)}
                value={algorithm.categoryMapID}
                to={algorithm.categoryMapURI}
              />
            </FormRow>
            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_VERSION)}
                value={algorithm.version}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_DESCRIPTION)}
                value={algorithm.description}
              />
            </FormRow>
          </FormSection>
        </>
      ) : error ? (
        <div className={styles.errorContent}>
          <ErrorState error={error} />
        </div>
      ) : null}
    </>
  )
}
