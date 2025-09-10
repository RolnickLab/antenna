import { useCreateProject } from 'data-services/hooks/projects/useCreateProject'
import { Project } from 'data-services/models/project'
import * as Dialog from 'design-system/components/dialog/dialog'
import { PlusIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { ProjectDetailsForm } from './project-details-form'
import styles from './styles.module.scss'

const CLOSE_TIMEOUT = 1000

const newProject = new Project({
  id: 'new-project',
})

export const NewProjectDialog = ({
  buttonSize = 'small',
  buttonVariant = 'outline',
}: {
  buttonSize?: string
  buttonVariant?: string
}) => {
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
        <Button size={buttonSize} variant={buttonVariant}>
          <PlusIcon className="w-4 h-4" />
          <span>{label}</span>
        </Button>
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
