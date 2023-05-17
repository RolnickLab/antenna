import { Deployment } from 'data-services/models/deployment'
import * as Dialog from 'design-system/components/dialog/dialog'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { DeploymentDetails } from './deployment-details'
import { DeploymentDetailsForm } from './deployment-details-form'

export const DeploymentDetailsDialog = ({
  deployment,
  open,
  onOpenChange,
}: {
  deployment?: Deployment
  open: boolean
  onOpenChange: () => void
}) => {
  const [isEditing, setIsEditing] = useState(false)

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        {deployment ? (
          !isEditing ? (
            <DeploymentDetails
              deployment={deployment}
              onEditClick={() => setIsEditing(true)}
            />
          ) : (
            <DeploymentDetailsForm
              deployment={deployment}
              onCancelClick={() => setIsEditing(false)}
            />
          )
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
