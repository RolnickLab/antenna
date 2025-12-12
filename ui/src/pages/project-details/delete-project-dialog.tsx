import classNames from 'classnames'
import { DeleteForm } from 'components/form/delete-form/delete-form'
import { useDeleteProject } from 'data-services/hooks/projects/useDeleteProject'
import * as Dialog from 'design-system/components/dialog/dialog'
import { TrashIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import styles from './styles.module.scss'

export const DeleteProjectDialog = ({ id }: { id: string }) => {
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const { deleteProject, isLoading, isSuccess, error } = useDeleteProject(() =>
    setTimeout(() => navigate(APP_ROUTES.HOME), 200)
  )

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <Button size="icon" variant="ghost">
          <TrashIcon className="w-4 h-4" />
        </Button>
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
