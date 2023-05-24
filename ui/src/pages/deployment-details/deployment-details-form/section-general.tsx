import { FormField } from 'components/form/form-field'
import {
  Deployment,
  DeploymentFieldValues,
} from 'data-services/models/deployment'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { InputValue } from 'design-system/components/input/input'
import _ from 'lodash'
import { useContext, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { isEmpty } from 'utils/isEmpty'
import { STRING, translate } from 'utils/language'
import styles from '../styles.module.scss'
import { config } from './config'
import { Section } from './deployment-details-form'
import { FormContext } from './formContext'

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
  onNext,
}: {
  deployment: Deployment
  onNext: () => void
}) => {
  const {
    formSectionRef,
    formState,
    setFormSectionStatus,
    setFormSectionValues,
  } = useContext(FormContext)

  const {
    control,
    handleSubmit,
    formState: { isDirty, isValid },
  } = useForm<SectionGeneralFieldValues>({
    defaultValues: {
      ...DEFAULT_VALUES,
      ..._.omitBy(formState[Section.General].values, isEmpty),
    },
    mode: 'onBlur',
  })

  useEffect(() => {
    setFormSectionStatus(Section.General, { isDirty, isValid })
  }, [isDirty, isValid])

  return (
    <form
      ref={formSectionRef}
      onSubmit={handleSubmit((values) =>
        setFormSectionValues(Section.General, values)
      )}
    >
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>
          {translate(STRING.DETAILS_LABEL_GENERAL)}
        </h2>
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
          <Button
            label={translate(STRING.NEXT)}
            onClick={onNext}
            theme={ButtonTheme.Success}
          />
        </div>
      </div>
    </form>
  )
}
