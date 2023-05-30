import { useContext, useEffect } from 'react'
import { Control, useFormState } from 'react-hook-form'
import { FormContext } from 'utils/formContext/formContext'
import { Section } from './deployment-details-form'

export const useSyncSectionStatus = (
  section: Section,
  control: Control<any, any>
) => {
  const { isDirty, isValid } = useFormState({ control })
  const { setFormSectionStatus } = useContext(FormContext)

  useEffect(() => {
    setFormSectionStatus(section, { isDirty, isValid })
  }, [isDirty, isValid])
}
