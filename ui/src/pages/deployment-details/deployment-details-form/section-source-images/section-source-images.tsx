import { FormController } from 'components/form/form-controller'
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
import { Button } from 'design-system/components/button/button'
import { InputContent } from 'design-system/components/input/input'
import _ from 'lodash'
import { EntitiesPicker } from 'pages/overview/entities/entities-picker'
import { useContext } from 'react'
import { useForm } from 'react-hook-form'
import { FormContext } from 'utils/formContext/formContext'
import { isEmpty } from 'utils/isEmpty/isEmpty'
import { STRING, translate } from 'utils/language'
import { useSyncSectionStatus } from 'utils/useSyncSectionStatus'
import { config } from '../config'
import { SectionExampleCaptures } from '../section-example-captures/section-example-captures'
import { Section } from '../types'

type SectionSourceImagesFieldValues = Pick<
  DeploymentFieldValues,
  'dataSourceId'
>

export const SectionSourceImages = ({
  deployment,
  onBack,
}: {
  deployment: DeploymentDetails
  onBack: () => void
}) => {
  const { formSectionRef, formState, setFormSectionValues } =
    useContext(FormContext)

  const { control, handleSubmit } = useForm<SectionSourceImagesFieldValues>({
    defaultValues: {
      ..._.omitBy(formState[Section.SourceImages].values, isEmpty),
    },
    mode: 'onBlur',
  })

  useSyncSectionStatus(Section.SourceImages, control)

  return (
    <form
      ref={formSectionRef}
      onSubmit={handleSubmit((values) =>
        setFormSectionValues(Section.SourceImages, values)
      )}
    >
      <FormSection title={translate(STRING.FIELD_LABEL_SOURCE_IMAGES)}>
        <FormRow>
          <FormController
            name="dataSourceId"
            control={control}
            config={config.deviceId}
            render={({ field, fieldState }) => (
              <InputContent
                description={config[field.name].description}
                label={config[field.name].label}
                error={fieldState.error?.message}
              >
                <EntitiesPicker
                  collection={API_ROUTES.STORAGE}
                  value={field.value}
                  onValueChange={field.onChange}
                />
              </InputContent>
            )}
          />
        </FormRow>
        <SectionExampleCaptures deployment={deployment} />
      </FormSection>
      <FormActions>
        <Button label={translate(STRING.BACK)} onClick={onBack} />
      </FormActions>
    </form>
  )
}
