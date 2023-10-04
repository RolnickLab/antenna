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
import { ImageCarousel } from 'design-system/components/image-carousel/image-carousel'
import { InputValue } from 'design-system/components/input/input'
import _ from 'lodash'
import { Status } from 'pages/deployment-details/connection-status/types'
import { useContext } from 'react'
import { useForm } from 'react-hook-form'
import { FormContext } from 'utils/formContext/formContext'
import { isEmpty } from 'utils/isEmpty/isEmpty'
import { STRING, translate } from 'utils/language'
import { useSyncSectionStatus } from 'utils/useSyncSectionStatus'
import { ConnectionStatus } from '../../connection-status/connection-status'
import { useConnectionStatus } from '../../connection-status/useConnectionStatus'
import styles from '../../styles.module.scss'
import { config } from '../config'
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
        {status === Status.Connected ? (
          <>
            <FormRow>
              <InputValue
                label={translate(STRING.FIELD_LABEL_CAPTURES)}
                value={deployment.numImages}
              />
              <InputValue
                label={translate(STRING.FIELD_LABEL_EXAMPLE_CAPTURES)}
                value={deployment.exampleCaptures.length}
              />
            </FormRow>
            <div className={styles.exampleCapturesContainer}>
              <ImageCarousel
                images={deployment.exampleCaptures}
                size={{ width: '100%', ratio: 16 / 9 }}
              />
            </div>
          </>
        ) : null}
      </FormSection>
      <FormActions>
        <Button label={translate(STRING.BACK)} onClick={onBack} />
      </FormActions>
    </form>
  )
}
