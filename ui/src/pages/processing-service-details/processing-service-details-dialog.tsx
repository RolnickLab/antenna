import { FormRow, FormSection } from 'components/form/layout/layout'
import { useProcessingServiceDetails } from 'data-services/hooks/processing-services/useProcessingServiceDetails'
import { ProcessingService } from 'data-services/models/processing-service'
import * as Dialog from 'design-system/components/dialog/dialog'
import { InputValue } from 'design-system/components/input/input'
import _ from 'lodash'
import { useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { ProcessingServicePipelines } from './processing-service-pipelines'
import styles from './styles.module.scss'

export const ProcessingServiceDetailsDialog = ({ id }: { id: string }) => {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const { processingService, isLoading, error } =
    useProcessingServiceDetails(id)

  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={() =>
        navigate(
          getAppRoute({
            to: APP_ROUTES.PROCESSING_SERVICES({
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
            type: _.capitalize(
              translate(STRING.ENTITY_TYPE_PROCESSING_SERVICE)
            ),
          })}
        />
        <div className={styles.content}>
          {processingService ? (
            <ProcessingServiceDetailsContent
              processingService={processingService}
            />
          ) : null}
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const ProcessingServiceDetailsContent = ({
  processingService,
}: {
  processingService: ProcessingService
}) => (
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
          label={translate(STRING.FIELD_LABEL_LAST_SEEN)}
          value={processingService.lastSeen}
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
          <ProcessingServicePipelines processingService={processingService} />
        </div>
      </FormSection>
    )}
  </>
)
