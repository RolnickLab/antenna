import { FormController } from 'components/form/form-controller'
import {
  FormActions,
  FormError,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { Export, SERVER_EXPORT_TYPES } from 'data-services/models/export'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { CaptureSetPicker } from 'design-system/components/capture-set-picker'
import { IconType } from 'design-system/components/icon/icon'
import { InputContent } from 'design-system/components/input/input'
import { Select } from 'design-system/components/select/select'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { DetailsFormProps, FormValues } from './types'

type ExportFormValues = FormValues & {
  type: string
  sourceImages: string
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
}

export const ExportDetailsForm = ({
  error,
  isLoading,
  isSuccess,
  onSubmit,
}: DetailsFormProps) => {
  const {
    control,
    handleSubmit,
    setError: setFieldError,
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
            >
              <CaptureSetPicker
                value={field.value}
                onValueChange={field.onChange}
              />
            </InputContent>
          )}
        />
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

export const TypePicker = ({
  value,
  onValueChange,
}: {
  value?: string
  onValueChange: (value?: string) => void
}) => (
  <Select
    showClear={false}
    options={SERVER_EXPORT_TYPES.map((key) => ({
      value: key,
      label: Export.getExportTypeInfo(key).label,
    }))}
    value={value}
    onValueChange={onValueChange}
  />
)
