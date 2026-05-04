import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { ProjectDetails } from 'data-services/models/project-details'
import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button, InputContent } from 'nova-ui-kit'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { PipelinesSelect } from './pipelines-select'

interface ProcessingFormValues {
  defaultProcessingPipeline: { id: string; name: string }
  sessionTimeGapSeconds: number
}

const config: FormConfig = {
  defaultProcessingPipeline: {
    label: 'Default processing pipeline',
    description:
      'The default pipeline to use for processing images in this project.',
  },
  sessionTimeGapSeconds: {
    label: 'Maximum time gap between sessions (default)',
    description:
      'Maximum time gap (in seconds) between consecutive images before a new session is started. Default is 7200 seconds (2 hours).',
    rules: { required: true, min: 1 },
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
      sessionTimeGapSeconds: project.settings.sessionTimeGapSeconds,
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
        <FormRow>
          <FormField
            name="sessionTimeGapSeconds"
            type="number"
            config={config}
            control={control}
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
