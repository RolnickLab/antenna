import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { StorageSource } from 'data-services/models/storage'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { Input, LockedInput } from 'design-system/components/input/input'
import { ConnectionStatus } from 'pages/overview/storage/connection-status'
import { useState } from 'react'
import {
  ControllerFieldState,
  ControllerRenderProps,
  FieldPath,
  FieldValues,
  useForm,
} from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps, FormValues } from './types'

type StorageFormValues = FormValues & {
  bucket: string
  public_base_url: string | undefined
  endpoint_url: string | undefined
  access_key: string | undefined
  secret_key: string | undefined
}

const config: FormConfig = {
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    description: 'A descriptive name for internal reference.',
    rules: {
      required: true,
    },
  },
  bucket: {
    label: 'Bucket/Container name',
    description: 'The root location within the storage service.',
    rules: {
      required: true,
    },
  },
  endpoint_url: {
    label: 'Endpoint URL',
    description:
      "Custom storage service endpoint. If not provided, the endpoint for Amazon's S3 service will be used.",
  },
  public_base_url: {
    label: 'Public base URL',
    description:
      'Base URL for public access to files. If not provided, temporary private URLs will be generated on-demand.',
  },
  access_key: {
    label: 'Access key ID',
    description: 'Access key ID for the S3 object storage service.',
  },
  secret_key: {
    label: 'Secret access key',
    description: 'Secret access key for the S3 object storage service.',
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
    setFocus,
  } = useForm<StorageFormValues>({
    defaultValues: {
      access_key: storage?.accessKey,
      name: storage?.name,
      bucket: storage?.bucket,
      public_base_url: storage?.publicBaseUrl,
      endpoint_url: storage?.endpointUrl,
      // Secret access key is not returned by the API
    },
    mode: 'onChange',
  })

  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form
      onSubmit={handleSubmit((values) =>
        onSubmit({
          name: values.name,
          customFields: {
            bucket: values.bucket,
            public_base_url: values.public_base_url,
            endpoint_url: values.endpoint_url,
            access_key: values.access_key,
            secret_key: values.secret_key,
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
            name="bucket"
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
            name="public_base_url"
            type="text"
            config={config}
            control={control}
          />
        </FormRow>
        <FormRow>
          <FormField
            name="access_key"
            type="text"
            config={config}
            control={control}
          />
          <FormController
            name="secret_key"
            control={control}
            config={config.access_key}
            render={({ field, fieldState }) => (
              <SecretKeyInput
                entityCreated={!!storage?.createdAt}
                field={field}
                fieldState={fieldState}
                onEditStart={() => setTimeout(() => setFocus(field.name))}
              />
            )}
          />
        </FormRow>
        {storage?.id && (
          <ConnectionStatus
            storageId={storage.id}
            updatedAt={storage.updatedAtDetailed}
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

const SecretKeyInput = <
  TFieldValues extends FieldValues,
  TName extends FieldPath<TFieldValues>
>({
  entityCreated,
  field,
  fieldState,
  onEditStart,
}: {
  entityCreated?: boolean
  field: ControllerRenderProps<TFieldValues, TName>
  fieldState: ControllerFieldState
  onEditStart?: () => void
}) => {
  const fieldConfig = config[field.name]
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState<string>(field.value)

  const maskedValue = field.value?.length
    ? field.value.replace(/./g, '*')
    : '************'

  if (!entityCreated) {
    return (
      <Input
        {...field}
        type="password"
        label={fieldConfig.label}
        description={fieldConfig.description}
        error={fieldState.error?.message}
      />
    )
  }

  return (
    <LockedInput
      editing={editing}
      setEditing={(editing) => {
        setEditing(editing)

        if (editing) {
          onEditStart?.()
        }
      }}
      onCancel={() => setEditValue(field.value)}
      onSubmit={() => field.onChange(editValue.length ? editValue : undefined)}
    >
      <Input
        {...field}
        type="password"
        label={fieldConfig.label}
        description={fieldConfig.description}
        error={fieldState.error?.message}
        disabled={!editing}
        value={!editing ? maskedValue : editValue ?? ''}
        onChange={(e) => setEditValue(e.currentTarget.value)}
      />
    </LockedInput>
  )
}
