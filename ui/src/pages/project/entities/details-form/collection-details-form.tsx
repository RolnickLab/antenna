import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { Collection } from 'data-services/models/capture-set'
import { SaveButton } from 'design-system/components/button/save-button'
import { InputContent } from 'design-system/components/input/input'
import { DatePicker } from 'design-system/components/select/date-picker'
import { XIcon } from 'lucide-react'
import { Button, Select } from 'nova-ui-kit'
import { SERVER_SAMPLING_METHODS } from 'pages/project/capture-sets/constants'
import { useForm } from 'react-hook-form'
import {
  formatIntegerList,
  parseIntegerList,
  validateInteger,
  validateIntegerList,
} from 'utils/fieldProcessors'
import { STRING, translate } from 'utils/language'
import { snakeCaseToSentenceCase } from 'utils/snakeCaseToSentenceCase'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps, FormValues } from './types'

type CollectionFormValues = FormValues & {
  method: string
  kwargs: {
    date_start: string | undefined
    date_end: string | undefined
    hour_start: number | undefined
    hour_end: number | undefined
    max_num: number | undefined
    minute_interval: number | undefined
    size: number | undefined
    deployment_ids: string | undefined
    research_site_ids: string | undefined
    event_ids: string | undefined
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
    label: 'Method',
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
    description: 'Enter a number between 0 and 24.',
    rules: {
      min: 0,
      max: 24,
      validate: validateInteger,
    },
  },
  'kwargs.hour_end': {
    label: 'Latest hour',
    description: 'Enter a number between 0 and 24.',
    rules: {
      min: 0,
      max: 24,
      validate: validateInteger,
    },
  },
  'kwargs.max_num': {
    label: 'Max number of captures',
    rules: {
      min: 0,
      validate: validateInteger,
    },
  },
  'kwargs.minute_interval': {
    label: 'Minutes between captures',
    rules: {
      min: 0,
      required: true,
      validate: validateInteger,
    },
  },
  'kwargs.size': {
    label: 'Number of captures',
    rules: {
      min: 0,
      required: true,
      validate: validateInteger,
    },
  },
  'kwargs.deployment_ids': {
    label: 'Station IDs',
    description: 'Enter comma-separated numbers (e.g., 1, 2, 3).',
    rules: {
      validate: validateIntegerList,
    },
    toApiValue: parseIntegerList,
    toFormValue: formatIntegerList,
  },
  'kwargs.event_ids': {
    label: 'Session IDs',
    description: 'Enter comma-separated numbers (e.g., 1, 2, 3).',
    rules: {
      validate: validateIntegerList,
    },
    toApiValue: parseIntegerList,
    toFormValue: formatIntegerList,
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
  const { control, handleSubmit, setError, watch } =
    useForm<CollectionFormValues>({
      defaultValues: {
        name: entity?.name ?? '',
        description: entity?.description ?? '',
        kwargs: {
          minute_interval: 10,
          size: 100,
          ...Object.fromEntries(
            Object.entries(collection?.kwargs || {}).map(([key, value]) => {
              const fieldConfig = config[`kwargs.${key}`]
              const formValue = fieldConfig?.toFormValue
                ? fieldConfig.toFormValue(value)
                : value
              return [key, formValue]
            })
          ),
        },
        method: collection?.method ?? SERVER_SAMPLING_METHODS[0],
      },
      mode: 'onChange',
    })
  const errorMessage = useFormError({ error, setFieldError: setError })
  const method = watch('method')

  return (
    <form
      onSubmit={handleSubmit((values) => {
        const processedKwargs = Object.fromEntries(
          Object.entries(values.kwargs)
            .filter(([key]) => {
              // Make sure method specific fields are only passed for related method
              if (key === 'max_num' || key === 'minute_interval') {
                return values.method === 'interval'
              }

              if (key === 'size') {
                return values.method === 'random'
              }

              return true
            })
            .map(([key, value]) => {
              const fieldConfig = config[`kwargs.${key}`]
              const processedValue = fieldConfig?.toApiValue
                ? fieldConfig.toApiValue(value)
                : value === ''
                ? null
                : value
              return [key, processedValue]
            })
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
                <div className="flex items-center justify-between gap-2">
                  <DatePicker
                    value={field.value}
                    onValueChange={field.onChange}
                  />
                  {field.value && (
                    <Button
                      size="icon"
                      className="shrink-0 text-muted-foreground"
                      variant="ghost"
                      onClick={() => field.onChange('')}
                    >
                      <XIcon className="w-4 h-4" />
                    </Button>
                  )}
                </div>
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
                <div className="flex items-center justify-between gap-2">
                  <DatePicker
                    value={field.value}
                    onValueChange={field.onChange}
                  />
                  {field.value && (
                    <Button
                      size="icon"
                      className="shrink-0 text-muted-foreground"
                      variant="ghost"
                      onClick={() => field.onChange('')}
                    >
                      <XIcon className="w-4 h-4" />
                    </Button>
                  )}
                </div>
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
        <FormRow>
          <FormField
            name="kwargs.deployment_ids"
            type="text"
            config={config}
            control={control}
          />
          <FormField
            name="kwargs.event_ids"
            type="text"
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
            name="method"
            control={control}
            config={config['method']}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={`${config[field.name].label} *`}
                error={fieldState.error?.message}
              >
                <SamplingTypePicker
                  value={field.value}
                  onValueChange={field.onChange}
                />
              </InputContent>
            )}
          />
          {method === 'interval' ? (
            <>
              <FormField
                name="kwargs.minute_interval"
                type="number"
                config={config}
                control={control}
              />
              <div />
              <FormField
                name="kwargs.max_num"
                type="number"
                config={config}
                control={control}
              />
            </>
          ) : null}
          {method === 'random' ? (
            <FormField
              name="kwargs.size"
              type="number"
              config={config}
              control={control}
            />
          ) : null}
        </FormRow>
      </FormSection>
      <FormActions>
        <SaveButton isLoading={isLoading} isSuccess={isSuccess} />
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
      {SERVER_SAMPLING_METHODS.map((samplingMethod) => (
        <Select.Item key={samplingMethod} value={samplingMethod}>
          {snakeCaseToSentenceCase(samplingMethod)}
        </Select.Item>
      ))}
    </Select.Content>
  </Select.Root>
)
