import { useUpdateDeployment } from 'data-services/hooks/deployments/useUpdateDeployment'
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
}) => (
  <Dialog.Root open={open} onOpenChange={onOpenChange}>
    <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
      {deployment ? (
        <DeploymentDetailsDialogContent deployment={deployment} />
      ) : null}
    </Dialog.Content>
  </Dialog.Root>
)

const DeploymentDetailsDialogContent = ({
  deployment,
}: {
  deployment: DeploymentDetails
}) => {
  const [isEditing, setIsEditing] = useState(false)
  const { updateDeployment, isLoading } = useUpdateDeployment(deployment?.id)

  useEffect(() => {
    // Reset to view mode when a new deployment is selected
    setIsEditing(false)
  }, [deployment?.id])

  return (
    <>
      {!isEditing ? (
        <DeploymentDetailsInfo
          deployment={deployment}
          title={translate(STRING.DETAILS_LABEL_DEPLOYMENT_DETAILS)}
          onEditClick={() => setIsEditing(true)}
        />
      ) : (
        <DeploymentDetailsForm
          deployment={deployment}
          isLoading={isLoading}
          startValid
          title={translate(STRING.DETAILS_LABEL_EDIT_DEPLOYMENT)}
          onCancelClick={() => setIsEditing(false)}
          onSubmit={(data) => {
            updateDeployment(data)
          }}
        />
      )}
    </>
  )
}
