import { FormField } from 'components/form/form-field'
import { isValid } from 'date-fns'

import {
  FormActions,
  FormError,
  FormRow,
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

type CollectionFormValues = FormValues & {
  method: string
  kwargs: {
    max_num: number | undefined
    minute_interval: number | undefined
    month_start: string | undefined
    month_end: string | undefined
    hour_start: number | undefined
    hour_end: number | undefined
    date_start: string | undefined
    date_end: string | undefined
  }
}

// simple date string config

const kwargs_date_config = {
  label: 'Date',
  description: 'Format: YYYY-MM-DD',
  rules: {
    validate: (value: any): string | undefined => {
      if (!value) return undefined

      if (!isValid(new Date(value))) {
        return 'Date must be in YYYY-MM-DD format'
      }

      return undefined
    },
  },
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
    description: 'When set, the collection will be a random sample',
  },
  'kwargs.minute_interval': {
    label: 'Minutes between captures',
  },
  'kwargs.month_start': {
    label: 'Earliest month',
  },
  'kwargs.month_end': {
    label: 'Latest month',
  },
  'kwargs.hour_start': {
    label: 'Earliest hour',
  },
  'kwargs.hour_end': {
    label: 'Latest hour',
  },
  'kwargs.date_start': {
    ...kwargs_date_config,
    label: 'Earliest date',
  },
  'kwargs.date_end': {
    ...kwargs_date_config,
    label: 'Latest date',
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
      onSubmit={handleSubmit((values) => {
        const processedKwargs = Object.fromEntries(
          Object.entries(values.kwargs).map(([key, value]) => [
            key,
            value === '' ? null : value,
          ])
        )

        onSubmit({
          name: values.name,
          description: values.description,
          customFields: {
            method: values.method,
            kwargs: processedKwargs,
          },
        })
      })}
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
            name="description"
            type="text"
            config={config}
            control={control}
          />
        </FormRow>
      </FormSection>
      <FormSection>
        <FormRow>
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
        </FormRow>
        <FormRow>
          <FormField
            name="kwargs.month_start"
            type="number"
            config={config}
            control={control}
          />
          <FormField
            name="kwargs.month_end"
            type="number"
            config={config}
            control={control}
          />
        </FormRow>
        <FormRow>
          <FormField
            name="kwargs.hour_start"
            type="number"
            config={config}
            control={control}
          />
          <FormField
            name="kwargs.hour_end"
            type="number"
            config={config}
            control={control}
          />
        </FormRow>
        <FormRow>
          <FormField
            name="kwargs.date_start"
            type="text"
            config={config}
            control={control}
          />
          <FormField
            name="kwargs.date_end"
            type="text"
            config={config}
            control={control}
          />
        </FormRow>
        <FormRow>
          <FormField
            name="method"
            type="text"
            config={config}
            control={control}
          />
        </FormRow>
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
