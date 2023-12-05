import { useUpdateEntity } from 'data-services/hooks/entities/useUpdateEntity'
import { Entity } from 'data-services/models/entity'
import * as Dialog from 'design-system/components/dialog/dialog'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { EntityDetailsForm } from './entity-details-form'
import styles from './styles.module.scss'

const CLOSE_TIMEOUT = 1000

export const EntityDetailsDialog = ({
  collection,
  entity,
  type,
}: {
  collection: string
  entity: Entity
  type: string
}) => {
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const { updateEntity, isLoading, isSuccess, error } = useUpdateEntity(
    entity.id,
    collection,
    () =>
      setTimeout(() => {
        setIsOpen(false)
      }, CLOSE_TIMEOUT)
  )

  const label = translate(STRING.ENTITY_EDIT, {
    type,
  })

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <button className={styles.dialogTrigger}>
          <span>{entity.name}</span>
        </button>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)} isCompact>
        <Dialog.Header title={label} />
        <div className={styles.dialogContent}>
          <EntityDetailsForm
            entity={entity}
            error={error}
            isLoading={isLoading}
            isSuccess={isSuccess}
            onSubmit={(data) => {
              updateEntity({
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
