import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { Backend } from 'data-services/models/backend'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { ConnectionStatus } from 'pages/overview/backends/connection-status'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps, FormValues } from './types'

type BackendFormValues = FormValues & {
  slug: string
  endpoint_url: string
  version_name: string | undefined
  version: number
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
    description: 'ML Backend Endpoint',
  },
  description: {
    label: translate(STRING.FIELD_LABEL_DESCRIPTION),
  },
  version_name: {
    label: translate(STRING.FIELD_LABEL_VERSION_NAME),
  },
  version: {
    label: translate(STRING.FIELD_LABEL_VERSION),
    rules: {
      required: true,
    },
  },
}

export const BackendDetailsForm = ({
  entity,
  error,
  isLoading,
  isSuccess,
  onSubmit,
}: DetailsFormProps) => {
  const backend = entity as Backend | undefined
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<BackendFormValues>({
    defaultValues: {
      endpoint_url: backend?.endpointUrl,
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
            version: values.version,
            version_name: values.version_name,
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
            name="version"
            type="number"
            config={config}
            control={control}
          />
          <FormField
            name="version_name"
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
        {backend?.id && (
          <ConnectionStatus
            backendId={backend.id}
            updatedAt={backend.updatedAtDetailed}
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
