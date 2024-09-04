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
import { Checkbox } from 'design-system/components/checkbox/checkbox'
import { IconType } from 'design-system/components/icon/icon'
import { ImageUpload } from 'design-system/components/image-upload/image-upload'
import { InputContent } from 'design-system/components/input/input'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { API_MAX_UPLOAD_SIZE, APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { bytesToMB } from 'utils/numberFormats'
import { useFormError } from 'utils/useFormError'
import styles from './styles.module.scss'

interface ProjectFormValues {
  name?: string
  description?: string
  image?: File | null
  openSource?: boolean
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
    rules: {
      required: true,
    },
  },
  image: {
    label: translate(STRING.FIELD_LABEL_IMAGE),
    description: [
      translate(STRING.MESSAGE_IMAGE_SIZE, {
        value: bytesToMB(API_MAX_UPLOAD_SIZE),
        unit: 'MB',
      }),
      translate(STRING.MESSAGE_IMAGE_FORMAT),
    ].join('\n'),
    rules: {
      validate: (file: File) => {
        if (file) {
          if (file?.size > API_MAX_UPLOAD_SIZE) {
            return translate(STRING.MESSAGE_IMAGE_TOO_BIG)
          }
        }
      },
    },
  },
  openSource: {
    label: translate(STRING.FIELD_LABEL_LICENSE),
    rules: {
      validate: (checked: boolean) => {
        if (!checked) {
          return translate(STRING.MESSAGE_LICENSE_REQUIRED)
        }
      },
    },
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
        <FormError
          inDialog
          intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
          message={errorMessage}
        />
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
                <ImageUpload
                  currentImage={project.image}
                  file={field.value}
                  name="image"
                  onChange={field.onChange}
                />
              </InputContent>
            )}
          />
        </FormRow>
        {project.createdAt ? null : (
          <FormRow>
            <FormController
              name="openSource"
              control={control}
              config={config.openSource}
              render={({ field, fieldState }) => (
                <InputContent
                  label={config.openSource.label}
                  style={{ gridColumn: 'span 2' }}
                  error={fieldState.error?.message}
                >
                  <div className={styles.checkboxList}>
                    <Checkbox
                      checked={field.value ?? false}
                      hasError={!!fieldState.error?.message?.length}
                      id={field.name}
                      innerRef={field.ref}
                      label={
                        <>
                          I want to contribute my data (uploaded and derived) to
                          the publicly available dataset. I release my data
                          under the{' '}
                          <a href="https://creativecommons.org/licenses/by-nc/4.0/?ref=chooser-v1">
                            Creative Commons Attribution-NonCommercial 4.0
                            International Public
                          </a>{' '}
                          open source license, in accordance with the{' '}
                          <Link to={APP_ROUTES.TERMS_OF_SERVICE}>
                            Terms of service
                          </Link>
                          .
                        </>
                      }
                      onCheckedChange={field.onChange}
                    />
                    <Checkbox
                      checked={false}
                      disabled
                      label={
                        <>
                          I do not want to contribute my data to the publicly
                          available dataset. My data will not be open sourced.{' '}
                          <i>(Option coming soon.)</i>
                        </>
                      }
                    />
                  </div>
                </InputContent>
              )}
            />
          </FormRow>
        )}
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
