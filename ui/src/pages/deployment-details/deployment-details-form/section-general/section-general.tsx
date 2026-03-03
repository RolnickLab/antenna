import { FormController } from 'components/form/form-controller'
import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { API_ROUTES } from 'data-services/constants'
import {
  DeploymentDetails,
  DeploymentFieldValues,
} from 'data-services/models/deployment-details'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { ImageUpload } from 'design-system/components/image-upload/image-upload'
import { InputContent } from 'design-system/components/input/input'
import { EntityPicker } from 'design-system/components/select/entity-picker'
import _ from 'lodash'
import { useContext } from 'react'
import { useForm } from 'react-hook-form'
import { FormContext } from 'utils/formContext/formContext'
import { isEmpty } from 'utils/isEmpty/isEmpty'
import { STRING, translate } from 'utils/language'
import { useSyncSectionStatus } from 'utils/useSyncSectionStatus'
import { config } from '../config'
import { Section } from '../types'

type SectionGeneralFieldValues = Pick<
  DeploymentFieldValues,
  'name' | 'description' | 'siteId' | 'deviceId' | 'image'
>

const DEFAULT_VALUES: SectionGeneralFieldValues = {
  description: '',
  name: '',
}

export const SectionGeneral = ({
  deployment,
  onNext,
}: {
  deployment: DeploymentDetails
  onNext: () => void
}) => {
  const { formSectionRef, formState, setFormSectionValues } =
    useContext(FormContext)

  const { control, handleSubmit } = useForm<SectionGeneralFieldValues>({
    defaultValues: {
      ...DEFAULT_VALUES,
      ..._.omitBy(formState[Section.General].values, isEmpty),
    },
    mode: 'onBlur',
  })

  useSyncSectionStatus(Section.General, control)

  return (
    <form
      ref={formSectionRef}
      onSubmit={handleSubmit((values) =>
        setFormSectionValues(Section.General, values)
      )}
    >
      <FormSection title={translate(STRING.FIELD_LABEL_GENERAL)}>
        <FormRow>
          <FormField name="name" control={control} config={config} />
          <FormField name="description" control={control} config={config} />
        </FormRow>
        <FormRow>
          <FormController
            name="siteId"
            control={control}
            config={config.siteId}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={config[field.name].label}
                error={fieldState.error?.message}
              >
                <EntityPicker
                  collection={API_ROUTES.SITES}
                  value={field.value}
                  onValueChange={field.onChange}
                />
              </InputContent>
            )}
          />
          <FormController
            name="deviceId"
            control={control}
            config={config.deviceId}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={config[field.name].label}
                error={fieldState.error?.message}
              >
                <EntityPicker
                  collection={API_ROUTES.DEVICES}
                  value={field.value}
                  onValueChange={field.onChange}
                />
              </InputContent>
            )}
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
                  currentImage={deployment.image}
                  file={field.value}
                  name="image"
                  onChange={field.onChange}
                />
              </InputContent>
            )}
          />
        </FormRow>
      </FormSection>
      <FormActions>
        <Button
          label={translate(STRING.NEXT)}
          onClick={onNext}
          theme={ButtonTheme.Success}
        />
      </FormActions>
    </form>
  )
}
