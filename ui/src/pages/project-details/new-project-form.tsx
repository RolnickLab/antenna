import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { SaveButton } from 'design-system/components/button/save-button'
import { InputContent } from 'design-system/components/input/input'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { PipelinesSelect } from './pipelines-select'

interface NewProjectFormValues {
  name?: string
  description?: string
  defaultProcessingPipeline: { id: string; name: string }
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
  defaultProcessingPipeline: {
    label: 'Default processing pipeline',
    description:
      'Based on the region of interest, select a default pipeline to use for processing in this project.',
  },
}

export const NewProjectForm = ({
  error,
  isLoading,
  isSuccess,
  onSubmit,
}: {
  error?: unknown
  isLoading?: boolean
  isSuccess?: boolean
  onSubmit: (data: NewProjectFormValues) => void
}) => {
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<NewProjectFormValues>({
    defaultValues: {
      name: '',
      description: '',
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
        <FormField name="name" type="text" config={config} control={control} />
        <FormField
          name="description"
          type="text"
          config={config}
          control={control}
        />

        <FormController
          name="defaultProcessingPipeline"
          control={control}
          config={config.defaultProcessingPipeline}
          render={({ field, fieldState }) => (
            <InputContent
              description={config[field.name].description}
              label={config[field.name].label}
              error={fieldState.error?.message}
            >
              <PipelinesSelect
                pipeline={field.value}
                onPipelineChange={field.onChange}
              />
            </InputContent>
          )}
        />
      </FormSection>
      <FormActions>
        <SaveButton isLoading={isLoading} isSuccess={isSuccess} />
      </FormActions>
    </form>
  )
}
