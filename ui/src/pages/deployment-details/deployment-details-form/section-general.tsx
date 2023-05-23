import { FormField } from 'components/form/form-field'
import {
  Deployment,
  DeploymentFieldValues,
} from 'data-services/models/deployment'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { InputValue } from 'design-system/components/input/input'
import _ from 'lodash'
import { useForm } from 'react-hook-form'
import { STRING, translate } from 'utils/language'
import styles from '../styles.module.scss'
import { config } from './config'

type SectionGeneralFieldValues = Pick<
  DeploymentFieldValues,
  'name' | 'device' | 'site'
>

const DEFAULT_VALUES: SectionGeneralFieldValues = {
  device: '',
  name: '',
  site: '',
}

export const SectionGeneral = ({
  deployment,
  onSubmit,
}: {
  deployment: Deployment
  onSubmit: (data: SectionGeneralFieldValues) => void
}) => {
  const { control, handleSubmit } = useForm<SectionGeneralFieldValues>({
    defaultValues: {
      ...DEFAULT_VALUES,
      ..._.omitBy(
        {
          name: deployment.name,
        },
        _.isUndefined
      ),
    },
    mode: 'onBlur',
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>General</h2>
        <div className={styles.sectionContent}>
          <div className={styles.sectionRow}>
            <InputValue
              label={translate(STRING.DETAILS_LABEL_DEPLOYMENT_ID)}
              value={deployment.id}
            />
            <FormField name="name" control={control} config={config} />
          </div>
          <div className={styles.sectionRow}>
            <FormField name="device" control={control} config={config} />
            <FormField name="site" control={control} config={config} />
          </div>
        </div>
        <div className={styles.formActions}>
          <Button label="Next" type="submit" theme={ButtonTheme.Success} />
        </div>
      </div>
    </form>
  )
}
