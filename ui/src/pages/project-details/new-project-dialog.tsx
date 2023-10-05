import { Project } from 'data-services/models/project'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { ProjectDetailsForm } from './project-details-form'
import styles from './styles.module.scss'

const newProject = new Project({
  id: 'new-project',
})

export const NewProjectDialog = () => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <Button
          label={translate(STRING.DIALOG_NEW_PROJECT)}
          icon={IconType.Plus}
          theme={ButtonTheme.Default}
        />
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        <Dialog.Header title={translate(STRING.DIALOG_NEW_PROJECT)} />
        <div className={styles.content}>
          <ProjectDetailsForm
            project={newProject}
            error={undefined}
            isLoading={false}
            onSubmit={async (data) => {
              /* TODO */
            }}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
