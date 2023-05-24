import { RefObject } from 'react'

export type FormState = {
  [section: string]: {
    isDirty?: boolean
    isValid?: boolean
    values?: any
  }
}

export interface FormContextValues {
  currentSection?: string
  formSectionRef?: RefObject<HTMLFormElement>
  formState: FormState
  setCurrentSection: (section: string) => void
  setFormSectionStatus: (
    section: string,
    status: { isValid: boolean; isDirty: boolean }
  ) => void
  setFormSectionValues: (section: string, values: any) => void
  submitFormSection: () => void
}
