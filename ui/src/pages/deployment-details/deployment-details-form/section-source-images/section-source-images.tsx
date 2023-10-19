import { FormField } from 'components/form/form-field'
import {
  FormActions,
  FormRow,
  FormSection,
} from 'components/form/layout/layout'
import {
  DeploymentDetails,
  DeploymentFieldValues,
} from 'data-services/models/deployment-details'
import { Button } from 'design-system/components/button/button'
import _ from 'lodash'
import { useContext } from 'react'
import { useForm } from 'react-hook-form'
import { FormContext } from 'utils/formContext/formContext'
import { isEmpty } from 'utils/isEmpty/isEmpty'
import { STRING, translate } from 'utils/language'
import { useSyncSectionStatus } from 'utils/useSyncSectionStatus'
import { ConnectionStatus } from '../../connection-status/connection-status'
import { useConnectionStatus } from '../../connection-status/useConnectionStatus'
import { config } from '../config'
import { SectionExampleCaptures } from '../section-example-captures/section-example-captures'
import { Section } from '../types'

type SectionSourceImagesFieldValues = Pick<DeploymentFieldValues, 'path'>

const DEFAULT_VALUES: SectionSourceImagesFieldValues = {
  path: '',
}

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
      ...DEFAULT_VALUES,
      ..._.omitBy(formState[Section.SourceImages].values, isEmpty),
    },
    mode: 'onBlur',
  })

  useSyncSectionStatus(Section.SourceImages, control)

  const { status, refreshStatus, lastUpdated } = useConnectionStatus(
    deployment?.path
  )

  return (
    <form
      ref={formSectionRef}
      onSubmit={handleSubmit((values) =>
        setFormSectionValues(Section.SourceImages, values)
      )}
    >
      <FormSection title={translate(STRING.FIELD_LABEL_SOURCE_IMAGES)}>
        <FormRow>
          <FormField name="path" control={control} config={config} />
          <ConnectionStatus
            status={status}
            onRefreshClick={refreshStatus}
            lastUpdated={lastUpdated}
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
