import classNames from 'classnames'
import { DeleteForm } from 'components/form/delete-form/delete-form'
import { useDeleteEntity } from 'data-services/hooks/entities/useDeleteEntity'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconButton } from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './styles.module.scss'

export const DeleteEntityDialog = ({
  collection,
  id,
}: {
  collection: string
  id: string
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const { deleteEntity, isLoading, isSuccess, error } =
    useDeleteEntity(collection)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <IconButton icon={IconType.RadixTrash} />
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        <div className={classNames(styles.deleteDialogContent)}>
          <DeleteForm
            error={error}
            type="object"
            isLoading={isLoading}
            isSuccess={isSuccess}
            onCancel={() => setIsOpen(false)}
            onSubmit={() => deleteEntity(id)}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
