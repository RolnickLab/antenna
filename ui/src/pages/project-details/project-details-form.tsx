import { FormController } from 'components/form/form-controller'
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
import { InputContent } from 'design-system/components/input/input'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import { useFormError } from 'utils/useFormError'
import { ProjectImageUpload } from './project-image-upload/project-image-upload'

interface ProjectFormValues {
  name?: string
  description?: string
  image?: File | null
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
  image: {
    label: 'Image',
    description: 'Valid formats are PNG, GIF and JPEG.',
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
        <FormRow>
          <FormController
            name="image"
            control={control}
            config={config.image}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={config[field.name].label}
                error={fieldState.error?.message}
              >
                <ProjectImageUpload
                  file={field.value}
                  project={project}
                  onChange={field.onChange}
                />
              </InputContent>
            )}
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
