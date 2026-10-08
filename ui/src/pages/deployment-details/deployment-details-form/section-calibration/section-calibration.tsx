import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import { DeploymentFieldValues } from 'data-services/models/deployment-details'
import _ from 'lodash'
import { Button } from 'nova-ui-kit'
import { useContext } from 'react'
import { useForm } from 'react-hook-form'
import { FormContext } from 'utils/formContext/formContext'
import { isEmpty } from 'utils/isEmpty/isEmpty'
import { STRING, translate } from 'utils/language'
import { useSyncSectionStatus } from 'utils/useSyncSectionStatus'
import { config } from '../config'
import { Section } from '../types'

type SectionCalibrationFieldValues = Pick<
  DeploymentFieldValues,
  'frameLongSideMm' | 'frameShortSideMm'
>

export const SectionCalibration = ({
  onBack,
  onNext,
}: {
  onBack: () => void
  onNext: () => void
}) => {
  const { formSectionRef, formState, setFormSectionValues } =
    useContext(FormContext)

  const { control, handleSubmit } = useForm<SectionCalibrationFieldValues>({
    defaultValues: _.omitBy(formState[Section.Calibration].values, isEmpty),
    mode: 'onBlur',
  })

  useSyncSectionStatus(Section.Calibration, control)

  return (
    <form
      ref={formSectionRef}
      onSubmit={handleSubmit((values) =>
        setFormSectionValues(Section.Calibration, values)
      )}
    >
      <FormSection
        title={translate(STRING.FIELD_LABEL_CALIBRATION)}
        description={translate(STRING.DESCRIPTION_FRAME_SIZE_MM)}
      >
        <FormRow>
          <FormField
            name="frameLongSideMm"
            control={control}
            config={config}
            type="number"
          />
          <FormField
            name="frameShortSideMm"
            control={control}
            config={config}
            type="number"
          />
        </FormRow>
      </FormSection>
      <FormActions>
        <Button onClick={onBack} size="small" type="button" variant="outline">
          <span>{translate(STRING.BACK)}</span>
        </Button>
        <Button onClick={onNext} size="small" type="button" variant="success">
          <span>{translate(STRING.NEXT)}</span>
        </Button>
      </FormActions>
    </form>
  )
}
