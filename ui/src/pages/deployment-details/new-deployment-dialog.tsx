import { useCreateDeployment } from 'data-services/hooks/deployments/useCreateDeployment'
import { DeploymentDetails } from 'data-services/models/deployment-details'
import * as Dialog from 'design-system/components/dialog/dialog'
import { PlusIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { DeploymentDetailsForm } from './deployment-details-form/deployment-details-form'

const newDeployment = new DeploymentDetails({
  id: 'new-deployment',
})

export const NewDeploymentDialog = () => {
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const { createDeployment, isLoading, error } = useCreateDeployment()

  const label = translate(STRING.ENTITY_CREATE, {
    type: translate(STRING.ENTITY_TYPE_DEPLOYMENT),
  })

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <Button size="small" variant="outline">
          <PlusIcon className="w-4 h-4" />
          <span>{label}</span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        <DeploymentDetailsForm
          deployment={newDeployment}
          serverError={error}
          isLoading={isLoading}
          title={label}
          onCancelClick={() => setIsOpen(false)}
          onSubmit={async (data) => {
            try {
              await createDeployment({ ...data, projectId })
              setIsOpen(false)
            } catch {
              // Error handled in hook
            }
          }}
        />
      </Dialog.Content>
    </Dialog.Root>
  )
}
