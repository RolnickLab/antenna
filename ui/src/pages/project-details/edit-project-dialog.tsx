import { ErrorState } from 'components/error-state/error-state'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { useUpdateProject } from 'data-services/hooks/projects/useUpdateProject'
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
        <Dialog.Header
          title={translate(STRING.ENTITY_EDIT, {
            type: translate(STRING.ENTITY_TYPE_PROJECT),
          })}
        />
        <div className={styles.content}>
          <EditProjectDialogContent id={id} onLoadingChange={setIsLoading} />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const EditProjectDialogContent = ({
  id,
  onLoadingChange,
}: {
  id: string
  onLoadingChange: (isLoading: boolean) => void
}) => {
  const { project, isLoading, error: loadError } = useProjectDetails(id)
  const {
    updateProject,
    isLoading: isUpdateLoading,
    isSuccess,
    error,
  } = useUpdateProject(id)

  useEffect(() => {
    onLoadingChange(isLoading)
  }, [isLoading])

  return (
    <div className={styles.content}>
      {project ? (
        <ProjectDetailsForm
          project={project}
          error={error}
          isLoading={isUpdateLoading}
          isSuccess={isSuccess}
          onSubmit={(data) => updateProject(data)}
        />
      ) : loadError ? (
        <div className={styles.errorContent}>
          <ErrorState error={error} />
        </div>
      ) : null}
    </div>
  )
}
