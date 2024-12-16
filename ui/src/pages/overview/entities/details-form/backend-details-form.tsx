import { FormController } from 'components/form/form-controller'
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
import { Input, LockedInput } from 'design-system/components/input/input'
import { ConnectionStatus } from 'pages/overview/backends/connection-status'
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

type BackendFormValues = FormValues & {
  endpoint_url: string | undefined
}

const config: FormConfig = {
  endpoint_url: {
    label: 'Endpoint URL',
    description: 'ML Backend Endpoint',
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
    setFocus,
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
            name="endpoint_url"
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

