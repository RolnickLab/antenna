import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { StorageSource } from 'data-services/models/storage'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps, FormValues } from './types'

type StorageFormValues = FormValues & {
  bucket: string
  public_base_url: string
  endpoint_url: string
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
  bucket: {
    label: 'Bucket',
  },
  public_base_url: {
    label: 'Public base URL',
  },
  endpoint_url: {
    label: 'Endpoint URL',
  },
}

export const StorageDetailsForm = ({
  entity,
  error,
  isLoading,
  isSuccess,
  onSubmit,
}: DetailsFormProps) => {
  const storage = entity as StorageSource | undefined
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<StorageFormValues>({
    defaultValues: {
      name: entity?.name ?? '',
      description: entity?.description ?? '',
      bucket: storage?.bucket ?? '',
      public_base_url: storage?.publicBaseUrl ?? '',
      endpoint_url: storage?.endpointUrl ?? '',
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
            bucket: values.bucket,
            public_base_url: values.public_base_url,
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
        <FormField name="name" type="text" config={config} control={control} />
        <FormField
          name="description"
          type="text"
          config={config}
          control={control}
        />
        <FormField
          name="bucket"
          type="text"
          config={config}
          control={control}
        />
        <FormField
          name="public_base_url"
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
