import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormMessage,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { API_ROUTES } from 'data-services/constants'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import {
  Checkbox,
  DocsLink,
  EntityPicker,
  InputContent,
  SaveButton,
  Select,
} from 'nova-ui-kit'
import { CaptureSetPicker } from 'nova-ui-kit/components/select/capture-set-picker'
import { useForm } from 'react-hook-form'
import { useParams } from 'react-router-dom'
import { APP_ROUTES, DOCS_LINKS } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { TrainClassifierFields } from './train-classifier-fields'
import { JOB_TYPE_ML, JOB_TYPE_TRAIN_CLASSIFIER, JobFormValues } from './types'

const config: FormConfig = {
  algorithmKey: {
    label: translate(STRING.FIELD_LABEL_ALGORITHM),
    description: translate(STRING.MESSAGE_TRAINING_ALGORITHM),
    rules: {
      required: true,
    },
  },
  jobType: {
    label: translate(STRING.FIELD_LABEL_JOB_TYPE),
    rules: {
      required: true,
    },
  },
  minPerSpecies: {
    label: translate(STRING.FIELD_LABEL_MIN_PER_SPECIES),
    description: translate(STRING.MESSAGE_MIN_PER_SPECIES),
    rules: {
      min: 1,
    },
  },
  occurrenceSet: {
    label: translate(STRING.FIELD_LABEL_OCCURRENCE_SET),
    description: translate(STRING.MESSAGE_TRAINING_OCCURRENCE_SET),
  },
  testFraction: {
    label: translate(STRING.FIELD_LABEL_TEST_FRACTION),
    description: translate(STRING.MESSAGE_TEST_FRACTION),
    rules: {
      min: 0.01,
      max: 0.99,
    },
  },
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
    rules: {
      required: true,
    },
  },
  sourceImages: {
    label: translate(STRING.FIELD_LABEL_CAPTURE_SET),
    rules: {
      required: true,
    },
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
  const { projectId } = useParams()
  const { project } = useProjectDetails(projectId as string, true)

  const {
    control,
    handleSubmit,
    setError: setFieldError,
    watch,
  } = useForm<JobFormValues>({
    defaultValues: {
      name: '',
      delay: 0,
      jobType: JOB_TYPE_ML,
      pipeline: project?.settings.defaultProcessingPipeline?.id,
      // Empty rather than unset: a retrain leaves these to the algorithm's own settings.
      testFraction: '',
      minPerSpecies: '',
    },
    mode: 'onChange',
    // Each job type shows its own fields, and the ones hidden must not hold back a
    // submission with rules that do not apply to the chosen type.
    shouldUnregister: true,
  })

  const jobType = watch('jobType')
  const isTraining = jobType === JOB_TYPE_TRAIN_CLASSIFIER

  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form onSubmit={handleSubmit((values) => onSubmit(values))}>
      {errorMessage ? (
        <FormError
          inDialog
          intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
          message={errorMessage}
        />
      ) : null}
      <FormSection>
        {!isTraining ? (
          <div className="flex flex-col items-end gap-4">
            <FormMessage
              message="Batch processing is currently in development and problems are likely to occur. If you need data processed, we recommend to reach out to the team for support. Thank you for your patience!"
              theme="warning"
              withIcon
            />
            <DocsLink href={DOCS_LINKS.PROCESSING_DATA} />
          </div>
        ) : null}
        <FormRow>
          <FormController
            name="jobType"
            control={control}
            config={config['jobType']}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={`${config[field.name].label} *`}
                error={fieldState.error?.message}
              >
                <JobTypePicker
                  value={field.value}
                  onValueChange={field.onChange}
                />
              </InputContent>
            )}
          />
        </FormRow>
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
        {isTraining ? (
          <TrainClassifierFields config={config} control={control} />
        ) : (
          <FormRow>
            <FormController
              name="sourceImages"
              control={control}
              config={config.sourceImages}
              render={({ field, fieldState }) => (
                <InputContent
                  description={config[field.name].description}
                  label={
                    config[field.name].rules?.required
                      ? `${config[field.name].label} *`
                      : config[field.name].label
                  }
                  error={fieldState.error?.message}
                  tooltip={{
                    text: translate(STRING.TOOLTIP_CAPTURE_SET),
                    link: {
                      text: translate(STRING.NAV_ITEM_CAPTURE_SETS),
                      to: APP_ROUTES.CAPTURE_SETS({
                        projectId: projectId as string,
                      }),
                    },
                  }}
                >
                  <CaptureSetPicker
                    onValueChange={field.onChange}
                    value={field.value}
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
                  label={
                    config[field.name].rules?.required
                      ? `${config[field.name].label} *`
                      : config[field.name].label
                  }
                  error={fieldState.error?.message}
                  tooltip={{
                    text: translate(STRING.TOOLTIP_PIPELINE),
                    link: {
                      text: translate(STRING.NAV_ITEM_PIPELINES),
                      to: APP_ROUTES.PIPELINES({
                        projectId: projectId as string,
                      }),
                    },
                  }}
                >
                  <EntityPicker
                    collection={API_ROUTES.PIPELINES}
                    onValueChange={field.onChange}
                    value={field.value}
                  />
                </InputContent>
              )}
            />
          </FormRow>
        )}
        <FormRow>
          <InputContent label="Config">
            <FormController
              name="startNow"
              control={control}
              config={config.startNow}
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
        <SaveButton isLoading={isLoading} isSuccess={isSuccess} />
      </FormActions>
    </form>
  )
}

export const JobTypePicker = ({
  value,
  onValueChange,
}: {
  value: string
  onValueChange: (value: string) => void
}) => {
  const options = [
    { value: JOB_TYPE_ML, label: translate(STRING.JOB_TYPE_ML) },
    {
      value: JOB_TYPE_TRAIN_CLASSIFIER,
      label: translate(STRING.JOB_TYPE_TRAIN_CLASSIFIER),
    },
  ]

  return (
    <Select.Root value={value ?? ''} onValueChange={onValueChange}>
      <Select.Trigger>
        <Select.Value />
      </Select.Trigger>
      <Select.Content>
        {options.map((option) => (
          <Select.Item key={option.value} value={option.value}>
            {option.label}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
