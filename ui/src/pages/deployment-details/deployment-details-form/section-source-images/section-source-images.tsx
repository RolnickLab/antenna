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
import { Button } from 'design-system/components/button/button'
import { InputContent, InputValue } from 'design-system/components/input/input'
import _ from 'lodash'
import { EntitiesPicker } from 'pages/overview/entities/entities-picker'
import { SyncStorage } from 'pages/overview/storage/storage-actions'
import { useContext } from 'react'
import { useForm } from 'react-hook-form'
import { FormContext } from 'utils/formContext/formContext'
import { isEmpty } from 'utils/isEmpty/isEmpty'
import { STRING, translate } from 'utils/language'
import { useSyncSectionStatus } from 'utils/useSyncSectionStatus'
import { config } from '../config'
import { SectionExampleCaptures } from '../section-example-captures/section-example-captures'
import { Section } from '../types'
import { SyncDeploymentSourceImages } from './actions/sync-source-images'

type SectionSourceImagesFieldValues = Pick<
  DeploymentFieldValues,
  'dataSourceId' | 'dataSourceSubdir' | 'dataSourceRegex'
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
      <FormSection title={translate(STRING.FIELD_LABEL_DATA_SOURCE)}>
        <FormRow>
          <FormController
            name="dataSourceId"
            control={control}
            config={config.dataSourceId}
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
          <FormField
            name="dataSourceSubdir"
            control={control}
            config={config}
          />
          <FormField name="dataSourceRegex" control={control} config={config} />
          {deployment.dataSource?.id && (
            <SyncStorage
              storageId={deployment.dataSource.id}
              subDir={deployment.dataSourceSubdir}
              regexFilter={deployment.dataSourceRegex}
            />
          )}
        </FormRow>
      </FormSection>
      <SectionDataSourceCaptures deployment={deployment} />
      <SectionExampleCaptures deployment={deployment} />
      <FormActions>
        <Button label={translate(STRING.BACK)} onClick={onBack} />
      </FormActions>
    </form>
  )
}

const SectionDataSourceCaptures = ({
  deployment,
}: {
  deployment: DeploymentDetails
}) => {
  if (!deployment?.dataSource?.id) {
    return (
      <FormSection
        title={translate(STRING.FIELD_LABEL_DATA_SOURCE_CAPTURES)}
        description={
          deployment?.createdAt
            ? translate(STRING.MESSAGE_DATA_SOURCE_NOT_CONFIGURED)
            : translate(STRING.MESSAGE_CAPTURE_SYNC_HIDDEN)
        }
      />
    )
  }

  return (
    <FormSection title={translate(STRING.FIELD_LABEL_DATA_SOURCE_CAPTURES)}>
      <FormRow>
        <InputValue
          label={translate(STRING.FIELD_LABEL_TOTAL_FILES)}
          value={deployment.numImages}
        />
        <InputValue
          label={translate(STRING.FIELD_LABEL_TOTAL_SIZE)}
          value={deployment.dataSourceDetails.totalSizeDisplay}
        />
        <div>
          <InputValue
            label={translate(STRING.FIELD_LABEL_LAST_SYNCED)}
            value={deployment.dataSourceDetails.lastChecked}
          />
          <SyncDeploymentSourceImages deploymentId={deployment.id} />
        </div>
      </FormRow>
    </FormSection>
  )
}
