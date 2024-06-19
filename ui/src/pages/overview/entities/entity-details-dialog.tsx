import classNames from 'classnames'
import { useUpdateEntity } from 'data-services/hooks/entities/useUpdateEntity'
import { Entity } from 'data-services/models/entity'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconButton } from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { customFormMap } from './details-form/constants'
import { EntityDetailsForm } from './details-form/entity-details-form'
import styles from './styles.module.scss'

const CLOSE_TIMEOUT = 1000

export const UpdateEntityDialog = ({
  collection,
  entity,
  type,
  isCompact,
}: {
  collection: string
  entity: Entity
  type: string
  isCompact?: boolean
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

  const DetailsForm = customFormMap[type] ?? EntityDetailsForm

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <IconButton icon={IconType.Pencil} />
      </Dialog.Trigger>
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isCompact={isCompact}
      >
        <Dialog.Header title={label} />
        <div
          className={classNames(styles.dialogContent, {
            [styles.compact]: isCompact,
          })}
        >
          <DetailsForm
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
