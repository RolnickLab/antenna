import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Checkbox } from 'design-system/components/checkbox/checkbox'
import { CollectionsPicker } from 'design-system/components/collections-picker'
import { IconType } from 'design-system/components/icon/icon'
import { InputContent } from 'design-system/components/input/input'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { PipelinesPicker } from './pipelines-picker'

interface JobFormValues {
  delay: number
  name: string
  pipeline?: string
  sourceImage?: string
  sourceImages?: string
  startNow?: boolean
}

const config: FormConfig = {
  delay: {
    label: translate(STRING.FIELD_LABEL_DELAY),
    rules: {
      required: true,
      min: 0,
    },
  },
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    rules: {
      required: true,
    },
  },
  pipeline: {
    label: translate(STRING.FIELD_LABEL_PIPELINE),
  },
  sourceImages: {
    label: translate(STRING.FIELD_LABEL_SOURCE_IMAGES),
  },
  startNow: {
    label: 'Start immediately',
  },
}

export const JobDetailsForm = ({
  error,
  isLoading,
  isSuccess,
  onSubmit,
}: {
  error?: unknown
  isLoading?: boolean
  isSuccess?: boolean
  onSubmit: (data: JobFormValues) => void
}) => {
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<JobFormValues>({
    defaultValues: {
      name: '',
      delay: 0,
    },
    mode: 'onChange',
  })

  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form onSubmit={handleSubmit((values) => onSubmit(values))}>
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
            name="delay"
            type="number"
            config={config}
            control={control}
          />
        </FormRow>
        <FormRow>
          <FormController
            name="sourceImages"
            control={control}
            config={config.sourceImages}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={config[field.name].label}
                error={fieldState.error?.message}
              >
                <CollectionsPicker
                  value={field.value}
                  onValueChange={field.onChange}
                />
              </InputContent>
            )}
          />
          <FormController
            name="pipeline"
            control={control}
            config={config.pipeline}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={config[field.name].label}
                error={fieldState.error?.message}
              >
                <PipelinesPicker
                  value={field.value}
                  onValueChange={field.onChange}
                />
              </InputContent>
            )}
          />
        </FormRow>
        <FormRow>
          <InputContent label="Config">
            <FormController
              name="startNow"
              control={control}
              config={config.pipeline}
              render={({ field }) => (
                <Checkbox
                  checked={field.value ?? false}
                  id={field.name}
                  label={config[field.name].label}
                  onCheckedChange={field.onChange}
                />
              )}
            />
          </InputContent>
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
