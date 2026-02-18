import { DeleteForm } from 'components/form/delete-form/delete-form'
import { useDeleteEntity } from 'data-services/hooks/entities/useDeleteEntity'
import * as Dialog from 'design-system/components/dialog/dialog'
import { TrashIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'

export const DeleteEntityDialog = ({
  collection,
  id,
  type,
}: {
  collection: string
  id: string
  type: string
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const { deleteEntity, isLoading, isSuccess, error } =
    useDeleteEntity(collection)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <Button className="shrink-0" size="icon" variant="ghost">
          <TrashIcon className="w-4 h-4" />
        </Button>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        <DeleteForm
          error={error}
          type={type}
          isLoading={isLoading}
          isSuccess={isSuccess}
          onCancel={() => setIsOpen(false)}
          onSubmit={() => deleteEntity(id)}
        />
      </Dialog.Content>
    </Dialog.Root>
  )
}
