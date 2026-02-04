import classNames from 'classnames'
import { API_ROUTES } from 'data-services/constants'
import { useCreateEntity } from 'data-services/hooks/entities/useCreateEntity'
import * as Dialog from 'design-system/components/dialog/dialog'
import { PlusIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { customFormMap } from './details-form/constants'
import { EntityDetailsForm } from './details-form/entity-details-form'
import styles from './styles.module.scss'

const CLOSE_TIMEOUT = 1000

export const NewEntityDialog = ({
  buttonSize = 'small',
  buttonVariant = 'outline',
  collection,
  isCompact,
  type,
}: {
  buttonSize?: string
  buttonVariant?: string
  collection: string
  isCompact?: boolean
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

  const DetailsForm = customFormMap[type] ?? EntityDetailsForm

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <Button size={buttonSize} variant={buttonVariant}>
          <PlusIcon className="w-4 h-4" />
          <span>{label}</span>
        </Button>
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
            error={error}
            isLoading={isLoading}
            isSuccess={isSuccess}
            onSubmit={(data) => {
              const fieldValues = {
                ...data,
                projectId: projectId as string,
              }

              createEntity(fieldValues)
            }}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
