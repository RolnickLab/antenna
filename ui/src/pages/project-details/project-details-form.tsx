import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormError,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { FormConfig } from 'components/form/types'
import { Project } from 'data-services/models/project'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'

interface ProjectFormValues {
  name?: string
  description?: string
}

const config: FormConfig = {
  name: {
    label: 'Name',
    rules: {
      required: true,
    },
  },
  description: {
    label: 'Description',
  },
}

export const ProjectDetailsForm = ({
  error,
  isLoading,
  isSuccess,
  project,
  onSubmit,
}: {
  error?: unknown
  isLoading?: boolean
  isSuccess?: boolean
  project: Project
  onSubmit: (data: ProjectFormValues) => void
}) => {
  const {
    control,
    handleSubmit,
    setError: setFieldError,
  } = useForm<ProjectFormValues>({
    defaultValues: {
      name: project.name ?? '',
      description: project.description ?? '',
    },
    mode: 'onChange',
  })

  const errorMessage = useFormError({ error, setFieldError })

  return (
    <form onSubmit={handleSubmit((values) => onSubmit(values))}>
      {errorMessage && (
        <FormError inDialog intro="Could not save" message={errorMessage} />
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
            name="description"
            type="text"
            config={config}
            control={control}
          />
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
