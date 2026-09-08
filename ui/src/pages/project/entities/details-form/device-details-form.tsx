import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormSection,
} from 'components/form/layout/layout'
import { MetadataField } from 'components/form/metadata-field'
import { FormConfig } from 'components/form/types'
import { Device } from 'data-services/models/device'
import { SaveButton } from 'nova-ui-kit'
import { useForm } from 'react-hook-form'
import {
  formatMetadata,
  parseMetadata,
  validateMetadata,
} from 'utils/fieldProcessors'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps, FormValues } from './types'

type DeviceFormValues = FormValues & {
  metadata: string
}

const config: FormConfig = {
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    rules: {
      required: true,
    },
  },
  description: {
    label: translate(STRING.FIELD_LABEL_DESCRIPTION),
  },
  metadata: {
    label: translate(STRING.FIELD_LABEL_METADATA),
    description: translate(STRING.MESSAGE_METADATA_DESCRIPTION),
    rules: {
      validate: validateMetadata,
    },
  },
}

/**
 * Device type form, which is the shared entity form plus free-form metadata, so
 * a project can record properties of its hardware that the platform has no
 * field of its own for.
 *
 * Metadata is edited as JSON text and becomes an object on the way to the API.
 * An invalid value stops the save, because react-hook-form only runs this
 * submit handler once every field passes its rules.
 */
export const DeviceDetailsForm = ({
  entity,
  error,
  isLoading,
  isSuccess,
  onSubmit,
}: DetailsFormProps) => {
  const device = entity as Device | undefined
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<DeviceFormValues>({
    defaultValues: {
      name: entity?.name ?? '',
      description: entity?.description ?? '',
      metadata: formatMetadata(device?.metadata),
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
            metadata: parseMetadata(values.metadata),
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
        <FormField name="name" type="text" config={config} control={control} />
        <FormField
          name="description"
          type="text"
          config={config}
          control={control}
        />
        <MetadataField name="metadata" control={control} config={config} />
      </FormSection>
      <FormActions>
        <SaveButton isLoading={isLoading} isSuccess={isSuccess} />
      </FormActions>
    </form>
  )
}
