import { Deployment } from 'data-services/models/deployment'
import * as Dialog from 'design-system/components/dialog/dialog'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { DeploymentDetailsForm } from './deployment-details-form'
import { DeploymentDetailsInfo } from './deployment-details-info'

export const DeploymentDetailsDialog = ({
  deployment,
  open,
  onOpenChange,
}: {
  deployment?: Deployment
  open: boolean
  onOpenChange: (open: boolean) => void
}) => {
  const [isEditing, setIsEditing] = useState(false)

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        {deployment ? (
          !isEditing ? (
            <DeploymentDetailsInfo
              deployment={deployment}
              title={translate(STRING.DETAILS_LABEL_DEPLOYMENT_DETAILS)}
              onEditClick={() => setIsEditing(true)}
            />
          ) : (
            <DeploymentDetailsForm
              deployment={deployment}
              title={translate(STRING.DETAILS_LABEL_EDIT_DEPLOYMENT)}
              onCancelClick={() => setIsEditing(false)}
              onSubmit={(data) => {
                console.log('onSubmit: ', data)
                onOpenChange(false)
              }}
            />
          )
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
