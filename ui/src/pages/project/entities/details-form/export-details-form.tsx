import { FormController } from 'components/form/form-controller'
import {
  FormActions,
  FormError,
  FormMessage,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { API_ROUTES } from 'data-services/constants'
import { Export, SERVER_EXPORT_TYPES } from 'data-services/models/export'
import { EntityPicker, InputContent, SaveButton, Select } from 'nova-ui-kit'
import { CaptureSetPicker } from 'nova-ui-kit/components/select/capture-set-picker'
import { useForm } from 'react-hook-form'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps, FormValues } from './types'

type ExportFormValues = FormValues & {
  type: string
  sourceImages?: string
  occurrenceSet?: string
}

const config: FormConfig = {
  type: {
    label: translate(STRING.FIELD_LABEL_TYPE),
    rules: {
      required: true,
    },
  },
  sourceImages: {
    label: translate(STRING.FIELD_LABEL_CAPTURE_SET),
  },
  occurrenceSet: {
    label: translate(STRING.FIELD_LABEL_OCCURRENCE_SET),
  },
}

export const ExportDetailsForm = ({
  error,
  isLoading,
  isSuccess,
  onSubmit,
}: DetailsFormProps) => {
  const { projectId } = useParams()
  const {
    control,
    handleSubmit,
    setError: setFieldError,
    setValue,
  } = useForm<ExportFormValues>({
    mode: 'onChange',
  })

  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form
      onSubmit={handleSubmit((values) =>
        onSubmit({
          name: '',
          customFields: {
            format: values.type,
            filters: {
              collection_id: values.sourceImages,
              occurrence_set_id: values.occurrenceSet,
            },
          },
        })
      )}
    >
      {errorMessage && (
        <FormError
          inDialog
          intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
          message={errorMessage}
        />
      )}
      <FormSection>
        <FormMessage message={translate(STRING.MESSAGE_EXPORT_TIP)} />
        <FormController
          name="type"
          control={control}
          config={config.type}
          render={({ field, fieldState }) => (
            <InputContent
              label={
                config[field.name].rules?.required
                  ? `${config[field.name].label} *`
                  : config[field.name].label
              }
              error={fieldState.error?.message}
            >
              <TypePicker value={field.value} onValueChange={field.onChange} />
            </InputContent>
          )}
        />
        <FormController
          name="sourceImages"
          control={control}
          config={config.sourceImages}
          render={({ field, fieldState }) => (
            <InputContent
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
                clearable
                onValueChange={(value) => {
                  field.onChange(value)
                  if (value) {
                    setValue('occurrenceSet', undefined)
                  }
                }}
                value={field.value}
              />
            </InputContent>
          )}
        />
        <FormController
          name="occurrenceSet"
          control={control}
          config={config.occurrenceSet}
          render={({ field, fieldState }) => (
            <InputContent
              label={config[field.name].label}
              error={fieldState.error?.message}
              tooltip={{ text: translate(STRING.TOOLTIP_OCCURRENCE_SET) }}
            >
              <EntityPicker
                clearable
                collection={API_ROUTES.OCCURRENCE_SET_CHOICES}
                onValueChange={(value) => {
                  field.onChange(value)
                  if (value) {
                    setValue('sourceImages', undefined)
                  }
                }}
                value={field.value}
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

export const TypePicker = ({
  value,
  onValueChange,
}: {
  value?: string
  onValueChange: (value?: string) => void
}) => (
  <Select.Root onValueChange={onValueChange} value={value ?? ''}>
    <Select.Trigger>
      <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
    </Select.Trigger>
    <Select.Content>
      {SERVER_EXPORT_TYPES.map((key) => (
        <Select.Item key={key} value={key}>
          {Export.getExportTypeInfo(key).label}
        </Select.Item>
      ))}
    </Select.Content>
  </Select.Root>
)
