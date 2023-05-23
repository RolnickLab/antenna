import {
  Deployment,
  DeploymentFieldValues,
} from 'data-services/models/deployment'
import { Button } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import styles from '../styles.module.scss'
import { SectionGeneral } from './section-general'
import { SectionLocation } from './section-location'
import { SectionSourceImages } from './section-source-images'

enum Section {
  General = 'general',
  Location = 'location',
  SourceImages = 'source-images',
}

export const DeploymentDetailsForm = ({
  deployment,
  title,
  onCancelClick,
  onSubmit,
}: {
  deployment: Deployment
  title: string
  onCancelClick: () => void
  onSubmit: (data: DeploymentFieldValues) => void
}) => {
  const [currentSection, setCurrentSection] = useState(Section.General)

  return (
    <>
      <Dialog.Header title={title}>
        <div className={styles.buttonWrapper}>
          <Button
            label={translate(STRING.CANCEL)}
            onClick={onCancelClick}
            type="button"
          />
        </div>
      </Dialog.Header>
      <div className={styles.content}>
        <SectionContent
          currentSection={currentSection}
          setCurrentSection={setCurrentSection}
          deployment={deployment}
        />
      </div>
    </>
  )
}

const SectionContent = ({
  currentSection,
  deployment,
  setCurrentSection,
}: {
  currentSection: Section
  deployment: Deployment
  setCurrentSection: (section: Section) => void
}) => {
  switch (currentSection) {
    case Section.General:
      return (
        <SectionGeneral
          deployment={deployment}
          onSubmit={(sectionData) => {
            console.log('sectionData: ', sectionData)
            setCurrentSection(Section.Location)
          }}
        />
      )
    case Section.Location:
      return (
        <SectionLocation
          deployment={deployment}
          onBack={() => setCurrentSection(Section.General)}
          onSubmit={(sectionData) => {
            console.log('sectionData: ', sectionData)
            setCurrentSection(Section.SourceImages)
          }}
        />
      )
    case Section.SourceImages:
      return (
        <SectionSourceImages
          deployment={deployment}
          onBack={() => setCurrentSection(Section.Location)}
          onSubmit={(sectionData) => console.log('sectionData: ', sectionData)}
        />
      )
  }
}
