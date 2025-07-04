import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { ProcessingService } from 'data-services/models/processing-service'
import { SaveButton } from 'design-system/components/button/save-button'
import { ConnectionStatus } from 'pages/project/processing-services/connection-status'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps, FormValues } from './types'

type ProcessingServiceFormValues = FormValues & {
  endpoint_url: string
}

const config: FormConfig = {
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    description: 'A descriptive name for internal reference.',
    rules: {
      required: true,
    },
  },
  endpoint_url: {
    label: 'Endpoint URL',
    description: 'Processing service endpoint.',
    rules: {
      required: true,
    },
  },
  description: {
    label: translate(STRING.FIELD_LABEL_DESCRIPTION),
  },
}

export const ProcessingServiceDetailsForm = ({
  entity,
  error,
  isLoading,
  isSuccess,
  onSubmit,
}: DetailsFormProps) => {
  const processingService = entity as ProcessingService | undefined
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<ProcessingServiceFormValues>({
    defaultValues: {
      name: processingService?.name,
      endpoint_url: processingService?.endpointUrl,
      description: processingService?.description ?? '',
    },
    mode: 'onChange',
  })

  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form
      onSubmit={handleSubmit((values) =>
        onSubmit({
          name: values.name,
          description: values.description,
          customFields: {
            endpoint_url: values.endpoint_url,
          },
        })
      )}
    >
      {errorMessage && (
        <FormError
          inDialog
          intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
          message={errorMessage}
        />
      )}
      <FormSection>
        <FormRow>
          <FormField
            name="name"
            type="text"
            config={config}
            control={control}
          />
          <FormField
            name="endpoint_url"
            type="text"
            config={config}
            control={control}
          />
        </FormRow>
        <FormRow>
          <FormField
            name="description"
            type="text"
            config={config}
            control={control}
          />
        </FormRow>
        {processingService?.id && (
          <ConnectionStatus
            processingServiceId={processingService.id}
            updatedAt={processingService.updatedAtDetailed}
          />
        )}
      </FormSection>
      <FormActions>
        <SaveButton isLoading={isLoading} isSuccess={isSuccess} />
      </FormActions>
    </form>
  )
}
