import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { Collection } from 'data-services/models/collection'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { editableSamplingMethods } from 'pages/overview/collections/constants'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps, FormValues } from './types'
// import { MethodEnum } from 'schema'

type CollectionFormValues = FormValues & {
  method: string,
  kwargs: {
    max_num: number | undefined,
    minute_interval: number | undefined,
    start_date: string | undefined,
    end_date: string | undefined,
  }
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
  method: {
    label: 'Sampling method',
    rules: {
      required: true,
      validate: (value: any) => {
        if (!editableSamplingMethods.includes(value)) {
          const validMethods = editableSamplingMethods.join(', ')
          return `Invalid method. Must be one of: ${validMethods}`
        }
      },
    },
  },
  'kwargs.max_num': {
    label: 'Max number of images',
  },
  'kwargs.minute_interval': {
    label: 'Minute interval',
  },
}

export const CollectionDetailsForm = ({
  entity,
  error,
  isLoading,
  isSuccess,
  onSubmit,
}: DetailsFormProps) => {
  const collection = entity as Collection | undefined
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<CollectionFormValues>({
    defaultValues: {
      name: entity?.name ?? '',
      description: entity?.description ?? '',
      method: collection?.method ?? editableSamplingMethods[0],
      kwargs: collection?.kwargs ?? {},
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
            method: values.method,
            kwargs: values.kwargs,
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
          name="kwargs.max_num"
          type="number"
          config={config}
          control={control}
        />
        <FormField
          name="kwargs.minute_interval"
          type="number"
          config={config}
          control={control}
        />
        <FormField
          name="method"
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
