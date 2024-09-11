import { FormRow, FormSection } from 'components/form/layout/layout'
import { usePipelineDetails } from 'data-services/hooks/pipelines/usePipelineDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputValue } from 'design-system/components/input/input'
import _ from 'lodash'
import { Error } from 'pages/error/error'
import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { PipelineAlgorithms } from './pipeline-algorithms'
import { PipelineStages } from './pipeline-stages'
import styles from './styles.module.scss'

export const PipelineDetailsDialog = ({
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
            type: _.capitalize(translate(STRING.ENTITY_TYPE_PIPELINE)),
          })}
        />
        <div className={styles.content}>
          <PipelineDetailsContent id={id} onLoadingChange={setIsLoading} />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const PipelineDetailsContent = ({
  id,
  onLoadingChange,
}: {
  id: string
  onLoadingChange: (isLoading: boolean) => void
}) => {
  const { pipeline, isLoading, error } = usePipelineDetails(id)

  useEffect(() => {
    onLoadingChange(isLoading)
  }, [isLoading])

  return (
    <>
      {pipeline ? (
        <>
          <FormSection title={translate(STRING.SUMMARY)}>
            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_ID)}
                value={pipeline.id}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_VERSION)}
                value={pipeline.versionLabel}
              />
            </FormRow>
            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_NAME)}
                value={pipeline.name}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_DESCRIPTION)}
                value={pipeline.description}
              />
            </FormRow>

            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_CREATED_AT)}
                value={pipeline.createdAt}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_UPDATED_AT)}
                value={pipeline.updatedAt}
              />
            </FormRow>
          </FormSection>
          {pipeline.stages.length > 1 && (
            <FormSection title={translate(STRING.STAGES)}>
              <PipelineStages pipeline={pipeline} />
            </FormSection>
          )}
          {pipeline.algorithms.length > 0 && (
            <FormSection title={translate(STRING.ALGORITHMS)}>
              <div className={styles.tableContainer}>
                <PipelineAlgorithms pipeline={pipeline} />
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
