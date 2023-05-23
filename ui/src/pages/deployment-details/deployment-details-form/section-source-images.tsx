import { FormField } from 'components/form/form-field'
import {
  Deployment,
  DeploymentFieldValues,
} from 'data-services/models/deployment'
import { Button } from 'design-system/components/button/button'
import _ from 'lodash'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import styles from '../styles.module.scss'
import { config } from './config'

type SectionSourceImagesFieldValues = Pick<DeploymentFieldValues, 'path'>

const DEFAULT_VALUES: SectionSourceImagesFieldValues = {
  path: '',
}

export const SectionSourceImages = ({
  deployment,
  onBack,
  onSubmit,
}: {
  deployment: Deployment
  onBack: () => void
  onSubmit: (data: SectionSourceImagesFieldValues) => void
}) => {
  const { control, handleSubmit } = useForm<SectionSourceImagesFieldValues>({
    defaultValues: {
      ...DEFAULT_VALUES,
      ..._.omitBy(
        {
          path: deployment.path,
        },
        _.isUndefined
      ),
    },
    mode: 'onBlur',
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>
          {translate(STRING.DETAILS_LABEL_SOURCE_IMAGES)}
        </h2>
        <div className={styles.sectionContent}>
          <div className={styles.sectionRow}>
            <FormField name="path" control={control} config={config} />
          </div>
        </div>
        <div className={styles.formActions}>
          <Button label={translate(STRING.BACK)} onClick={onBack} />
        </div>
      </div>
    </form>
  )
}
