import { FormRow, FormSection } from 'components/form/layout/layout'
import { usePipelineDetails } from 'data-services/hooks/pipelines/usePipelineDetails'
import { Pipeline } from 'data-services/models/pipeline'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputValue } from 'design-system/components/input/input'
import _ from 'lodash'
import { useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { PipelineAlgorithms } from './pipeline-algorithms'
import { PipelineStages } from './pipeline-stages'
import styles from './styles.module.scss'

export const PipelineDetailsDialog = ({ id }: { id: string }) => {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const { pipeline, isLoading, error } = usePipelineDetails(id)

  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={() =>
        navigate(
          getAppRoute({
            to: APP_ROUTES.PIPELINES({
              projectId: projectId as string,
            }),
            keepSearchParams: true,
          })
        )
      }
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
        error={error}
      >
        <Dialog.Header
          title={translate(STRING.ENTITY_DETAILS, {
            type: _.capitalize(translate(STRING.ENTITY_TYPE_PIPELINE)),
          })}
        />
        <div className={styles.content}>
          {pipeline ? <PipelineDetailsContent pipeline={pipeline} /> : null}
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const PipelineDetailsContent = ({ pipeline }: { pipeline: Pipeline }) => (
  <>
    <FormSection title={translate(STRING.SUMMARY)}>
      <FormRow>
        <InputValue
          label={translate(STRING.FIELD_LABEL_ID)}
          value={pipeline.id}
        />
        <InputValue
          label={translate(STRING.FIELD_LABEL_NAME)}
          value={pipeline.name}
        />
      </FormRow>
      <FormRow>
        <InputValue
          label={translate(STRING.FIELD_LABEL_VERSION)}
          value={pipeline.versionLabel}
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
)
