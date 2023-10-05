import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconButton } from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { ProjectDetailsForm } from './project-details-form'
import styles from './styles.module.scss'

export const EditProjectDialog = ({ id }: { id: string }) => {
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <IconButton icon={IconType.Pencil} />
      </Dialog.Trigger>
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
      >
        <Dialog.Header title={translate(STRING.DIALOG_EDIT_PROJECT)} />
        <div className={styles.content}>
          <EditProjectDialogContent
            id={id}
            onLoaded={() => setIsLoading(false)}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const EditProjectDialogContent = ({
  id,
  onLoaded,
}: {
  id: string
  onLoaded: () => void
}) => {
  const { project, isLoading } = useProjectDetails(id)

  useEffect(() => {
    if (!isLoading) {
      onLoaded()
    }
  }, [isLoading])

  return (
    <div className={styles.content}>
      {project && (
        <ProjectDetailsForm
          project={project}
          error={undefined}
          isLoading={false}
          onSubmit={async (data) => {
            /* TODO */
          }}
        />
      )}
    </div>
  )
}
