import classNames from 'classnames'
import { useCreateEntity } from 'data-services/hooks/entities/useCreateEntity'
import { PlusIcon } from 'lucide-react'
import { Button, Dialog } from 'nova-ui-kit'
import { RegisterPipelinesStep } from 'pages/project/processing-services/register-pipelines-step'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { customFormMap } from './details-form/constants'
import { EntityDetailsForm } from './details-form/entity-details-form'
import styles from './styles.module.scss'

const CLOSE_TIMEOUT = 1000

// A newly created processing service still has to be registered before its pipelines
// exist, so its dialog stays open on a "Register pipelines" step instead of closing.
const REQUIRES_REGISTRATION_TYPE = 'service'

export const NewEntityDialog = ({
  buttonSize = 'small',
  buttonVariant = 'outline',
  collection,
  isCompact,
  type,
}: {
  buttonSize?: 'default' | 'small'
  buttonVariant?: 'outline' | 'success'
  collection: string
  isCompact?: boolean
  type: string
}) => {
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const [createdServiceId, setCreatedServiceId] = useState<string>()
  const { createEntity, isLoading, isSuccess, error } = useCreateEntity(
    collection,
    (created) => {
      // Falling back to closing keeps the dialog usable if the id is ever missing,
      // rather than opening a registration step that would call an invalid URL.
      if (type === REQUIRES_REGISTRATION_TYPE && created.id !== undefined) {
        setCreatedServiceId(`${created.id}`)
        return
      }
      setTimeout(() => {
        setIsOpen(false)
      }, CLOSE_TIMEOUT)
    }
  )

  const label = translate(STRING.ENTITY_CREATE, {
    type,
  })

  const DetailsForm = customFormMap[type] ?? EntityDetailsForm

  const handleOpenChange = (open: boolean) => {
    setIsOpen(open)
    if (!open) {
      setCreatedServiceId(undefined)
    }
  }

  return (
    <Dialog.Root open={isOpen} onOpenChange={handleOpenChange}>
      <Dialog.Trigger asChild>
        <Button size={buttonSize} variant={buttonVariant}>
          <PlusIcon className="w-4 h-4" />
          <span>{label}</span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isCompact={isCompact || !!createdServiceId}
      >
        {createdServiceId ? (
          <RegisterPipelinesStep
            onDone={() => handleOpenChange(false)}
            processingServiceId={createdServiceId}
            projectId={projectId as string}
          />
        ) : (
          <>
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
          </>
        )}
      </Dialog.Content>
    </Dialog.Root>
  )
}
