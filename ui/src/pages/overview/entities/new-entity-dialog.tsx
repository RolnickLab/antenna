import { useCreateEntity } from 'data-services/hooks/entities/useCreateEntity'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { EntityDetailsForm } from './entity-details-form'
import styles from './styles.module.scss'

const CLOSE_TIMEOUT = 1000

export const NewEntityDialog = ({
  collection,
  type,
}: {
  collection: string
  type: string
}) => {
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const { createEntity, isLoading, isSuccess, error } = useCreateEntity(
    collection,
    () =>
      setTimeout(() => {
        setIsOpen(false)
      }, CLOSE_TIMEOUT)
  )

  const label = translate(STRING.ENTITY_CREATE, {
    type,
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
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        <Dialog.Header title={label} />
        <div className={styles.dialogContent}>
          <EntityDetailsForm
            error={error}
            isLoading={isLoading}
            isSuccess={isSuccess}
            onSubmit={(data) => {
              createEntity({
                ...data,
                projectId: projectId as string,
              })
            }}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
