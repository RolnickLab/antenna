/* eslint-disable @typescript-eslint/no-empty-function */

import {
  createContext,
  ReactNode,
  RefObject,
  useCallback,
  useMemo,
  useRef,
  useState,
} from 'react'

type FormState = {
  [section: string]: {
    isDirty?: boolean
    isValid?: boolean
    values?: any
  }
}

interface FormContextValues {
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

export const FormContext = createContext<FormContextValues>({
  currentSection: undefined,
  formState: {},
  setCurrentSection: () => {},
  setFormSectionStatus: () => {},
  setFormSectionValues: () => {},
  submitFormSection: () => {},
})

export const FormContextProvider = ({
  defaultSection,
  defaultFormState = {},
  children,
}: {
  defaultSection?: string
  defaultFormState?: FormState
  children: ReactNode
}) => {
  const formSectionRef = useRef<HTMLFormElement>(null)
  const [currentSection, _setCurrentSection] = useState(defaultSection)
  const [formState, setFormState] = useState<FormState>(defaultFormState)

  const currentSectionValid = useMemo(() => {
    if (!currentSection) {
      return false
    }
    return !!formState[currentSection].isValid
  }, [formState, currentSection])

  const setFormSectionStatus = useCallback(
    (section: string, status: { isValid: boolean; isDirty: boolean }) => {
      if (!formState[section].isDirty) {
        formState[section].isDirty = status.isDirty
      }
      formState[section].isValid = status.isValid
      setFormState({ ...formState })
    },
    [formState]
  )

  const setFormSectionValues = useCallback(
    (section: string, values: any) => {
      formState[section].values = values
      setFormState({ ...formState })
    },
    [formState]
  )

  const submitFormSection = useCallback(() => {
    formSectionRef?.current?.dispatchEvent(
      new Event('submit', { cancelable: true, bubbles: true })
    )
  }, [formSectionRef])

  const setCurrentSection = useCallback(
    (section: string) => {
      submitFormSection()

      if (currentSectionValid) {
        _setCurrentSection(section)
      }
    },
    [currentSectionValid, submitFormSection]
  )

  return (
    <FormContext.Provider
      value={{
        currentSection,
        formSectionRef,
        formState,
        setCurrentSection,
        setFormSectionStatus,
        setFormSectionValues,
        submitFormSection,
      }}
    >
      {children}
    </FormContext.Provider>
  )
}
