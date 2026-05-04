import { FormController } from 'components/form/form-controller'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { ProjectDetails } from 'data-services/models/project-details'
import { InputContent } from 'design-system/components/input/input'
import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { PipelinesSelect } from './pipelines-select'

interface ProcessingFormValues {
  defaultProcessingPipeline: { id: string; name: string }
}

const config: FormConfig = {
  defaultProcessingPipeline: {
    label: 'Default processing pipeline',
    description:
      'The default pipeline to use for processing images in this project.',
  },
}

export const ProcessingForm = ({
  error,
  isLoading,
  isSuccess,
  onSubmit,
  project,
}: {
  error?: unknown
  isLoading?: boolean
  isSuccess?: boolean
  onSubmit: (data: ProcessingFormValues) => void
  project: ProjectDetails
}) => {
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<ProcessingFormValues>({
    defaultValues: {
      defaultProcessingPipeline: project.settings.defaultProcessingPipeline,
    },
    mode: 'onChange',
  })

  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form
      onSubmit={handleSubmit((values) => {
        onSubmit(values)
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
        </FormRow>
      </FormSection>
      <FormActions>
        <Button size="small" type="submit" variant="success">
          <span>
            {isSuccess ? translate(STRING.SAVED) : translate(STRING.SAVE)}
          </span>
          {isSuccess ? (
            <CheckIcon className="w-4 h-4 ml-2" />
          ) : isLoading ? (
            <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
          ) : null}
        </Button>
      </FormActions>
    </form>
  )
}
