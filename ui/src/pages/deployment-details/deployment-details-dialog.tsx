import { DeploymentDetails } from 'data-services/models/deployment-details'
import * as Dialog from 'design-system/components/dialog/dialog'
import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { DeploymentDetailsForm } from './deployment-details-form/deployment-details-form'
import { DeploymentDetailsInfo } from './deployment-details-info'

export const DeploymentDetailsDialog = ({
  deployment,
  open,
  onOpenChange,
}: {
  deployment?: DeploymentDetails
  open: boolean
  onOpenChange: (open: boolean) => void
}) => {
  const [isEditing, setIsEditing] = useState(false)

  useEffect(() => {
    // Reset to view mode when a new deployment is selected
    setIsEditing(false)
  }, [deployment?.id])

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
              startValid
              title={translate(STRING.DETAILS_LABEL_EDIT_DEPLOYMENT)}
              onCancelClick={() => setIsEditing(false)}
              onSubmit={(data) => {
                // TODO: Hook up with BE
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
