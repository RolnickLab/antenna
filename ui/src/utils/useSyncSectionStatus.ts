import { useContext, useEffect } from 'react'
import { Control, useFormState } from 'react-hook-form'
import { FormContext } from 'utils/formContext/formContext'

export const useSyncSectionStatus = (
  section: string,
  control: Control<any, any>
) => {
  const { isDirty, isValid } = useFormState({ control })
  const { setFormSectionStatus } = useContext(FormContext)

  // Do not add setFormSectionStatus to the deps. It is memoised on the form state
  // that it replaces, so depending on its identity makes this effect loop forever.
  useEffect(() => {
    setFormSectionStatus(section, { isDirty, isValid })
  }, [isDirty, isValid])
}
