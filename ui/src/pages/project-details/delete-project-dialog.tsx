import classNames from 'classnames'
import { DeleteForm } from 'components/form/delete-form/delete-form'
import { useDeleteProject } from 'data-services/hooks/projects/useDeleteProject'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconButton } from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './styles.module.scss'

export const DeleteProjectDialog = ({ id }: { id: string }) => {
  const [isOpen, setIsOpen] = useState(false)
  const { deleteProject, isLoading, isSuccess, error } = useDeleteProject()

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <IconButton icon={IconType.RadixTrash} />
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        <div className={classNames(styles.content, styles.compact)}>
          <DeleteForm
            error={error}
            type={translate(STRING.ENTITY_TYPE_PROJECT)}
            isLoading={isLoading}
            isSuccess={isSuccess}
            onCancel={() => setIsOpen(false)}
            onSubmit={() => deleteProject(id)}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
