import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import {
  toTrackingScope,
  TrackingScope,
} from 'data-services/models/tracking-job'
import { Checkbox, InputContent, SaveButton, Select } from 'nova-ui-kit'
import { CaptureSetPicker } from 'nova-ui-kit/components/select/capture-set-picker'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'

interface TrackingJobFormValues {
  captureSetId?: string
  costThreshold?: string
  name: string
  requireFeatures: boolean
  scopeType: TrackingScope['type']
  sessionId?: string
  startNow: boolean
}

export interface TrackingJobSubmitValues {
  costThreshold?: string
  name: string
  requireFeatures: boolean
  scope: TrackingScope
  startNow: boolean
}

const config: FormConfig = {
  captureSetId: {
    label: translate(STRING.FIELD_LABEL_CAPTURE_SET),
    rules: { required: true },
  },
  costThreshold: {
    label: translate(STRING.TRACKING_JOB_COST_THRESHOLD),
    description: translate(STRING.TRACKING_JOB_COST_THRESHOLD_DESCRIPTION),
    rules: { min: 0 },
  },
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    description: translate(STRING.TRACKING_JOB_NAME_DESCRIPTION),
  },
  requireFeatures: {
    label: translate(STRING.TRACKING_JOB_REQUIRE_FEATURES),
    description: translate(STRING.TRACKING_JOB_REQUIRE_FEATURES_DESCRIPTION),
  },
  scopeType: {
    label: translate(STRING.TRACKING_JOB_SCOPE),
  },
  sessionId: {
    label: translate(STRING.FIELD_LABEL_SESSION_NUMBER),
    rules: { required: true, min: 1 },
  },
  startNow: {
    label: translate(STRING.TRACKING_JOB_START_NOW),
  },
}

export const TrackingJobForm = ({
  error,
  isLoading,
  isSuccess,
  onSubmit,
  scope,
}: {
  error?: unknown
  isLoading?: boolean
  isSuccess?: boolean
  onSubmit: (values: TrackingJobSubmitValues) => void
  /** Fixes what is tracked, hiding the scope fields; left out, the user picks one. */
  scope?: TrackingScope
}) => {
  const {
    control,
    handleSubmit,
    setError: setFieldError,
    watch,
  } = useForm<TrackingJobFormValues>({
    defaultValues: {
      name: '',
      requireFeatures: true,
      scopeType: scope?.type ?? 'session',
      startNow: true,
    },
    mode: 'onChange',
  })
  const scopeType = watch('scopeType')
  // Only the name maps onto a server field; errors about the params, which carry the
  // scope and settings, are shown above the form instead of on a hidden field.
  const errorMessage = useFormError({
    error,
    fields: ['name'],
    setFieldError,
  })

  return (
    <form
      onSubmit={handleSubmit(
        ({ captureSetId, scopeType, sessionId, ...values }) => {
          const chosenScope =
            scope ?? toTrackingScope({ captureSetId, scopeType, sessionId })

          if (chosenScope) {
            onSubmit({ ...values, scope: chosenScope })
          }
        }
      )}
    >
      {errorMessage ? (
        <FormError
          inDialog
          intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
          message={errorMessage}
        />
      ) : null}
      <FormSection description={translate(STRING.TRACKING_JOB_DESCRIPTION)}>
        {scope ? null : (
          <FormRow>
            <FormController
              name="scopeType"
              control={control}
              config={config.scopeType}
              render={({ field }) => (
                <InputContent label={config[field.name].label}>
                  <Select.Root
                    onValueChange={field.onChange}
                    value={field.value}
                  >
                    <Select.Trigger>
                      <Select.Value />
                    </Select.Trigger>
                    <Select.Content>
                      <Select.Item value="session">
                        {translate(STRING.TRACKING_JOB_SCOPE_SESSION)}
                      </Select.Item>
                      <Select.Item value="captureSet">
                        {translate(STRING.TRACKING_JOB_SCOPE_CAPTURE_SET)}
                      </Select.Item>
                    </Select.Content>
                  </Select.Root>
                </InputContent>
              )}
            />
            {scopeType === 'session' ? (
              <FormField
                name="sessionId"
                type="number"
                config={config}
                control={control}
              />
            ) : (
              <FormController
                name="captureSetId"
                control={control}
                config={config.captureSetId}
                render={({ field, fieldState }) => (
                  <InputContent
                    label={`${config[field.name].label} *`}
                    error={fieldState.error?.message}
                  >
                    <CaptureSetPicker
                      onValueChange={field.onChange}
                      value={field.value}
                    />
                  </InputContent>
                )}
              />
            )}
          </FormRow>
        )}
        <FormRow>
          <FormField
            name="name"
            type="text"
            config={config}
            control={control}
          />
          <FormField
            name="costThreshold"
            type="number"
            step={0.01}
            config={config}
            control={control}
          />
        </FormRow>
        <FormRow>
          <InputContent
            label={translate(STRING.TRACKING_JOB_OPTIONS)}
            description={config.requireFeatures.description}
          >
            <div className="grid gap-2">
              <FormController
                name="requireFeatures"
                control={control}
                config={config.requireFeatures}
                render={({ field }) => (
                  <Checkbox
                    checked={field.value}
                    id={field.name}
                    label={config[field.name].label}
                    onCheckedChange={field.onChange}
                  />
                )}
              />
              <FormController
                name="startNow"
                control={control}
                config={config.startNow}
                render={({ field }) => (
                  <Checkbox
                    checked={field.value}
                    id={field.name}
                    label={config[field.name].label}
                    onCheckedChange={field.onChange}
                  />
                )}
              />
            </div>
          </InputContent>
        </FormRow>
      </FormSection>
      <FormActions>
        <SaveButton isLoading={isLoading} isSuccess={isSuccess} />
      </FormActions>
    </form>
  )
}
