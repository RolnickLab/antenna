import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { Collection } from 'data-services/models/collection'
import { InputContent } from 'design-system/components/input/input'
import { DatePicker } from 'design-system/components/select/date-picker'
import { Loader2Icon } from 'lucide-react'
import { Button, Select } from 'nova-ui-kit'
import { SAMPLING_TYPES } from 'pages/project/collections/constants'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { snakeCaseToSentenceCase } from 'utils/snakeCaseToSentenceCase'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps, FormValues } from './types'

type CollectionFormValues = FormValues & {
  type: string
  kwargs: {
    date_start: string | undefined
    date_end: string | undefined
    hour_start: number | undefined
    hour_end: number | undefined
    max_num: number | undefined
    minute_interval: number | undefined
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
  type: {
    label: 'Type',
    rules: {
      required: true,
    },
  },
  'kwargs.date_start': {
    label: 'Earliest date',
  },
  'kwargs.date_end': {
    label: 'Latest date',
  },
  'kwargs.hour_start': {
    label: 'Earliest hour',
  },
  'kwargs.hour_end': {
    label: 'Latest hour',
  },
  'kwargs.max_num': {
    label: 'Max number of images',
    rules: {
      required: true,
    },
  },
  'kwargs.minute_interval': {
    label: 'Minutes between captures',
    rules: {
      required: true,
    },
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
  const { control, handleSubmit, setError, setValue, watch } =
    useForm<CollectionFormValues>({
      defaultValues: {
        name: entity?.name ?? '',
        description: entity?.description ?? '',
        type: collection?.type ?? SAMPLING_TYPES[0],
        kwargs: collection?.kwargs ?? {},
      },
      mode: 'onChange',
    })
  const errorMessage = useFormError({ error, setFieldError: setError })
  const type = watch('type')

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
            method: 'common_combined',
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
        <h3 className="body-large font-bold text-muted-foreground/50">
          General
        </h3>
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
        <h3 className="body-large font-bold text-muted-foreground/50">
          Filters
        </h3>
        <FormRow>
          <FormController
            name="kwargs.date_start"
            control={control}
            config={config['kwargs.date_start']}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={config[field.name].label}
                error={fieldState.error?.message}
              >
                <DatePicker
                  value={field.value}
                  onValueChange={field.onChange}
                />
              </InputContent>
            )}
          />
          <FormController
            name="kwargs.date_end"
            control={control}
            config={config['kwargs.date_end']}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={config[field.name].label}
                error={fieldState.error?.message}
              >
                <DatePicker
                  value={field.value}
                  onValueChange={field.onChange}
                />
              </InputContent>
            )}
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
      </FormSection>
      <FormSection>
        <h3 className="body-large font-bold text-muted-foreground/50">
          Sampling settings
        </h3>
        <FormRow>
          <FormController
            name="type"
            control={control}
            config={config['type']}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={`${config[field.name].label} *`}
                error={fieldState.error?.message}
              >
                <SamplingTypePicker
                  value={field.value}
                  onValueChange={(value) => {
                    field.onChange(value)

                    // Reset sample settings when type is updated
                    setValue('kwargs.max_num', undefined)
                    setValue('kwargs.minute_interval', undefined)
                  }}
                />
              </InputContent>
            )}
          />
          {type === 'random_sample' ? (
            <FormField
              name="kwargs.max_num"
              type="number"
              config={config}
              control={control}
            />
          ) : null}
          {type === 'interval_sample' ? (
            <FormField
              name="kwargs.minute_interval"
              type="number"
              config={config}
              control={control}
            />
          ) : null}
        </FormRow>
      </FormSection>
      <FormActions>
        <Button size="small" type="submit">
          <span>
            {isSuccess ? translate(STRING.SAVED) : translate(STRING.SAVE)}
          </span>
          {isLoading ? (
            <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
          ) : null}
        </Button>
      </FormActions>
    </form>
  )
}

export const SamplingTypePicker = ({
  value,
  onValueChange,
}: {
  value: string
  onValueChange: (value: string) => void
}) => (
  <Select.Root value={value ?? ''} onValueChange={onValueChange}>
    <Select.Trigger>
      <Select.Value />
    </Select.Trigger>
    <Select.Content>
      {SAMPLING_TYPES.map((samplingType) => (
        <Select.Item key={samplingType} value={samplingType}>
          {snakeCaseToSentenceCase(samplingType)}
        </Select.Item>
      ))}
    </Select.Content>
  </Select.Root>
)
