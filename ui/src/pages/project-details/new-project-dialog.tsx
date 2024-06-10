import { useCreateProject } from 'data-services/hooks/projects/useCreateProject'
import { Project } from 'data-services/models/project'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { ProjectDetailsForm } from './project-details-form'
import styles from './styles.module.scss'

const CLOSE_TIMEOUT = 1000

const newProject = new Project({
  id: 'new-project',
})

export const NewProjectDialog = () => {
  const [isOpen, setIsOpen] = useState(false)
  const { createProject, isLoading, isSuccess, error } = useCreateProject(() =>
    setTimeout(() => {
      setIsOpen(false)
    }, CLOSE_TIMEOUT)
  )

  const label = translate(STRING.ENTITY_CREATE, {
    type: translate(STRING.ENTITY_TYPE_PROJECT),
  })

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <Button
          label={label}
          icon={IconType.Plus}
          theme={ButtonTheme.Default}
        />
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        <Dialog.Header title={label} />
        <div className={styles.content}>
          <ProjectDetailsForm
            project={newProject}
            error={error}
            isLoading={isLoading}
            isSuccess={isSuccess}
            onSubmit={(data) => createProject(data)}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
