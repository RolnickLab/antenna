import classNames from 'classnames'
import { DeleteForm } from 'components/form/delete-form/delete-form'
import { useDeleteJob } from 'data-services/hooks/jobs/useDeleteJob'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconButton } from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './jobs.module.scss'

export const DeleteJobsDialog = ({
  id,
  onDelete,
}: {
  id: string
  onDelete?: () => void
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const { deleteJob, isLoading, isSuccess, error } = useDeleteJob(onDelete)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <IconButton icon={IconType.RadixTrash} />
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        <div className={classNames(styles.dialogContent)}>
          <DeleteForm
            error={error}
            type="job"
            isLoading={isLoading}
            isSuccess={isSuccess}
            onCancel={() => setIsOpen(false)}
            onSubmit={() => deleteJob(id)}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
