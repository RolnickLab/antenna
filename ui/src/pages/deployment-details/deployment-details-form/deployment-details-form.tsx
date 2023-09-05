import {
  DeploymentDetails,
  DeploymentFieldValues,
} from 'data-services/models/deployment-details'
import { parseServerError } from 'data-services/utils'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { FormStepper as _FormStepper } from 'design-system/components/form-stepper/form-stepper'
import { useCallback, useContext, useMemo } from 'react'
import { FormContext, FormContextProvider } from 'utils/formContext/formContext'
import { STRING, translate } from 'utils/language'
import styles from '../styles.module.scss'
import { SectionGeneral } from './section-general/section-general'
import { SectionLocation } from './section-location/section-location'
import { SectionSourceImages } from './section-source-images/section-source-images'
import { Section } from './types'

export const DeploymentDetailsForm = ({
  deployment,
  serverError,
  isLoading,
  startValid,
  title,
  onCancelClick,
  onSubmit,
}: {
  deployment: DeploymentDetails
  serverError?: any
  isLoading?: boolean
  startValid?: boolean
  title: string
  onCancelClick: () => void
  onSubmit: (data: DeploymentFieldValues) => void
}) => (
  <FormContextProvider
    defaultSection={Section.General}
    defaultFormState={{
      [Section.General]: {
        values: {
          name: deployment.name,
          description: deployment.description,
        },
        isValid: startValid,
      },
      [Section.Location]: {
        values: {
          latitude: deployment.latitude,
          longitude: deployment.longitude,
        },
        isValid: startValid,
      },
      [Section.SourceImages]: {
        values: {
          path: deployment.path,
        },
        isValid: startValid,
      },
    }}
  >
    <Dialog.Header title={title}>
      <div className={styles.buttonWrapper}>
        <Button
          label={translate(STRING.CANCEL)}
          onClick={onCancelClick}
          type="button"
        />
        <SaveButton isLoading={isLoading} onSubmit={onSubmit} />
      </div>
    </Dialog.Header>
    {serverError && <FormError error={serverError} />}
    <div className={styles.content}>
      <div className={styles.section}>
        <FormStepper />
      </div>
      <FormSection deployment={deployment} />
    </div>
  </FormContextProvider>
)

const SaveButton = ({
  isLoading,
  onSubmit,
}: {
  isLoading?: boolean
  onSubmit: (data: DeploymentFieldValues) => void
}) => {
  const { formState, submitFormSection } = useContext(FormContext)

  const allValid = useMemo(() => {
    const someInvalid = Object.values(formState).some(
      (section) => !section.isValid
    )
    return !someInvalid
  }, [formState])

  const someDirty = useMemo(() => {
    const someDirty = Object.values(formState).some(
      (section) => section.isDirty
    )
    return someDirty
  }, [formState])

  const onSaveClick = useCallback(() => {
    submitFormSection()
    requestAnimationFrame(() => {
      const data = Object.values(formState).reduce((result: any, section) => {
        if (section.isValid) {
          result = { ...result, ...section.values }
        }
        return result
      }, {})
      onSubmit(data)
    })
  }, [formState, submitFormSection])

  return (
    <Button
      disabled={!allValid || !someDirty || isLoading}
      label={translate(STRING.SAVE)}
      loading={isLoading}
      theme={ButtonTheme.Success}
      onClick={onSaveClick}
    />
  )
}

const FormStepper = () => {
  const { currentSection, setCurrentSection } = useContext(FormContext)

  return (
    <_FormStepper
      items={[
        {
          id: Section.General,
          label: translate(STRING.FIELD_LABEL_GENERAL),
        },
        {
          id: Section.Location,
          label: translate(STRING.FIELD_LABEL_LOCATION),
        },
        {
          id: Section.SourceImages,
          label: translate(STRING.FIELD_LABEL_SOURCE_IMAGES),
        },
      ]}
      currentItemId={currentSection}
      setCurrentItemId={setCurrentSection}
    />
  )
}

const FormSection = ({ deployment }: { deployment: DeploymentDetails }) => {
  const { currentSection, setCurrentSection } = useContext(FormContext)

  switch (currentSection) {
    case Section.General:
      return (
        <SectionGeneral onNext={() => setCurrentSection(Section.Location)} />
      )
    case Section.Location:
      return (
        <SectionLocation
          onBack={() => setCurrentSection(Section.General)}
          onNext={() => setCurrentSection(Section.SourceImages)}
        />
      )
    case Section.SourceImages:
      return (
        <SectionSourceImages
          deployment={deployment}
          onBack={() => setCurrentSection(Section.Location)}
        />
      )
    default:
      return null
  }
}

const FormError = ({ error }: { error: any }) => {
  const message = parseServerError(error).message

  return (
    <div className={styles.formError}>
      <span>Could not save: </span>
      <span>{message}</span>
    </div>
  )
}
