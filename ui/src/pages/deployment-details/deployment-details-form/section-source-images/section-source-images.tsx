import { FormField } from 'components/form/form-field'
import { DeploymentFieldValues } from 'data-services/models/deployment'
import { Button } from 'design-system/components/button/button'
import _ from 'lodash'
import { useContext } from 'react'
import { useForm } from 'react-hook-form'
import { FormContext } from 'utils/formContext/formContext'
import { isEmpty } from 'utils/isEmpty/isEmpty'
import { STRING, translate } from 'utils/language'
import { useSyncSectionStatus } from 'utils/useSyncSectionStatus'
import styles from '../../styles.module.scss'
import { config } from '../config'
import { Section } from '../types'

type SectionSourceImagesFieldValues = Pick<DeploymentFieldValues, 'path'>

const DEFAULT_VALUES: SectionSourceImagesFieldValues = {
  path: '',
}

export const SectionSourceImages = ({ onBack }: { onBack: () => void }) => {
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

  return (
    <form
      ref={formSectionRef}
      onSubmit={handleSubmit((values) =>
        setFormSectionValues(Section.SourceImages, values)
      )}
    >
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
