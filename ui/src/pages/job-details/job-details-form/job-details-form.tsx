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
import { Job, ServerJobType } from 'data-services/models/job'
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
import { TrainableAlgorithmPicker } from './trainable-algorithm-picker'

interface JobFormValues {
  algorithm?: string
  delay: number
  jobType: ServerJobType
  name: string
  occurrenceSet?: string
  pipeline?: string
  sourceImage?: string
  sourceImages?: string
  startNow?: boolean
}

// What each job type asks for. The backend refuses a job missing any of these, so the
// form hides the fields a type does not use and requires the ones it does.
const FIELDS_BY_JOB_TYPE: {
  [key in CreatableJobType]: (keyof JobFormValues)[]
} = {
  ml: ['sourceImages', 'pipeline'],
  generate_embeddings: ['pipeline', 'sourceImages'],
  train_classifier: ['algorithm'],
  evaluate_algorithm: ['algorithm', 'occurrenceSet'],
}

const CREATABLE_JOB_TYPES = Object.keys(
  FIELDS_BY_JOB_TYPE
) as CreatableJobType[]

type CreatableJobType = Extract<
  ServerJobType,
  'ml' | 'generate_embeddings' | 'train_classifier' | 'evaluate_algorithm'
>

const config: FormConfig = {
  algorithm: {
    label: translate(STRING.FIELD_LABEL_ALGORITHM),
    rules: {
      required: true,
    },
  },
  delay: {
    label: translate(STRING.FIELD_LABEL_DELAY),
    rules: {
      required: true,
      min: 0,
    },
  },
  jobType: {
    label: translate(STRING.FIELD_LABEL_TYPE),
    rules: {
      required: true,
    },
  },
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    rules: {
      required: true,
    },
  },
  occurrenceSet: {
    label: translate(STRING.FIELD_LABEL_EVALUATION_SET),
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
      jobType: 'ml',
      pipeline: project?.settings.defaultProcessingPipeline?.id,
    },
    mode: 'onChange',
  })

  const jobType = watch('jobType') as CreatableJobType
  const fields = FIELDS_BY_JOB_TYPE[jobType] ?? FIELDS_BY_JOB_TYPE.ml
  const shows = (field: keyof JobFormValues) => fields.includes(field)
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
        <div className="flex flex-col items-end gap-4">
          <FormMessage
            message="Batch processing is currently in development and problems are likely to occur. If you need data processed, we recommend to reach out to the team for support. Thank you for your patience!"
            theme="warning"
            withIcon
          />
          <DocsLink href={DOCS_LINKS.PROCESSING_DATA} />
        </div>
        <FormRow>
          <FormField
            name="name"
            type="text"
            config={config}
            control={control}
          />
          <FormController
            name="jobType"
            control={control}
            config={config.jobType}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={`${config[field.name].label} *`}
                error={fieldState.error?.message}
              >
                <Select.Root onValueChange={field.onChange} value={field.value}>
                  <Select.Trigger>
                    <Select.Value />
                  </Select.Trigger>
                  <Select.Content>
                    {CREATABLE_JOB_TYPES.map((key) => (
                      <Select.Item key={key} value={key}>
                        {Job.getJobTypeInfo(key).label}
                      </Select.Item>
                    ))}
                  </Select.Content>
                </Select.Root>
              </InputContent>
            )}
          />
        </FormRow>
        <FormRow>
          <FormField
            name="delay"
            type="number"
            config={config}
            control={control}
          />
        </FormRow>
        <FormRow>
          {shows('sourceImages') ? (
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
          ) : null}
          {shows('pipeline') ? (
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
          ) : null}
          {shows('algorithm') ? (
            <FormController
              name="algorithm"
              control={control}
              config={config.algorithm}
              render={({ field, fieldState }) => (
                <InputContent
                  description={config[field.name].description}
                  label={`${config[field.name].label} *`}
                  error={fieldState.error?.message}
                  tooltip={{
                    text: translate(STRING.TOOLTIP_ALGORITHM),
                    link: {
                      text: translate(STRING.NAV_ITEM_ALGORITHMS),
                      to: APP_ROUTES.ALGORITHMS({
                        projectId: projectId as string,
                      }),
                    },
                  }}
                >
                  <TrainableAlgorithmPicker
                    onValueChange={field.onChange}
                    value={field.value}
                  />
                </InputContent>
              )}
            />
          ) : null}
          {shows('occurrenceSet') ? (
            <FormController
              name="occurrenceSet"
              control={control}
              config={config.occurrenceSet}
              render={({ field, fieldState }) => (
                <InputContent
                  description={config[field.name].description}
                  label={`${config[field.name].label} *`}
                  error={fieldState.error?.message}
                  tooltip={{ text: translate(STRING.TOOLTIP_EVALUATION_SET) }}
                >
                  <EntityPicker
                    collection={API_ROUTES.OCCURRENCE_SETS}
                    onValueChange={field.onChange}
                    value={field.value}
                  />
                </InputContent>
              )}
            />
          ) : null}
        </FormRow>
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
