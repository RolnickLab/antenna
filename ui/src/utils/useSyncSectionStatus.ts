import { useContext, useEffect } from 'react'
import { Control, useFormState } from 'react-hook-form'
import { FormContext } from 'utils/formContext/formContext'

export const useSyncSectionStatus = (
  section: string,
  control: Control<any, any>
) => {
  const { isDirty, isValid } = useFormState({ control })
  const { setFormSectionStatus } = useContext(FormContext)

  useEffect(() => {
    setFormSectionStatus(section, { isDirty, isValid })
  }, [isDirty, isValid])
}
