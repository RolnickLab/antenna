import { FormRow, FormSection } from 'components/form/layout/layout'
import { usePipelineDetails } from 'data-services/hooks/pipelines/usePipelineDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputValue } from 'design-system/components/input/input'
import _ from 'lodash'
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
  const [isLoaded, setIsLoaded] = useState(false)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <button className={styles.dialogTrigger}>
          <span>{name}</span>
        </button>
      </Dialog.Trigger>
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={!isLoaded}
      >
        <Dialog.Header
          title={translate(STRING.ENTITY_DETAILS, {
            type: _.capitalize(translate(STRING.ENTITY_TYPE_PIPELINE)),
          })}
        />
        <div className={styles.content}>
          <PipelineDetailsContent id={id} onLoaded={() => setIsLoaded(true)} />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const PipelineDetailsContent = ({
  id,
  onLoaded,
}: {
  id: string
  onLoaded: () => void
}) => {
  const { pipeline, isLoading } = usePipelineDetails(id)

  useEffect(() => {
    if (!isLoading) {
      onLoaded()
    }
  }, [isLoading])

  return (
    <>
      {pipeline && (
        <>
          <FormSection title={translate(STRING.SUMMARY)}>
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
                label={translate(STRING.FIELD_LABEL_VERSION)}
                value={pipeline.versionLabel}
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
          {pipeline.stages.length > 0 && (
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
      )}
    </>
  )
}
