import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { ProcessingService } from 'data-services/models/processing-service'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { ConnectionStatus } from 'pages/overview/processing-services/connection-status'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps, FormValues } from './types'

type ProcessingServiceFormValues = FormValues & {
  slug: string
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
  slug: {
    label: translate(STRING.FIELD_LABEL_SLUG),
    description: 'A unique identifier for internal reference.',
    rules: {
      required: true,
    },
  },
  endpoint_url: {
    label: 'Endpoint URL',
    description: 'Processing Service Endpoint',
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
      name: processingService?.name ?? '',
      slug: processingService?.slug ?? '',
      endpoint_url: processingService?.endpointUrl ?? '',
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
            slug: values.slug,
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
            name="slug"
            type="text"
            config={config}
            control={control}
          />
        </FormRow>
        <FormRow>
          <FormField
            name="endpoint_url"
            type="text"
            config={config}
            control={control}
          />
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
        <Button
          label={isSuccess ? translate(STRING.SAVED) : translate(STRING.SAVE)}
          icon={isSuccess ? IconType.RadixCheck : undefined}
          type="submit"
          theme={ButtonTheme.Success}
          loading={isLoading}
        />
      </FormActions>
    </form>
  )
}
