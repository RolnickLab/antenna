import { useDeploymentDetails } from 'data-services/hooks/deployments/useDeploymentsDetails'
import { useUpdateDeployment } from 'data-services/hooks/deployments/useUpdateDeployment'
import { DeploymentDetails } from 'data-services/models/deployment-details'
import * as Dialog from 'design-system/components/dialog/dialog'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { DeploymentDetailsForm } from './deployment-details-form/deployment-details-form'
import { DeploymentDetailsInfo } from './deployment-details-info'

export const DeploymentDetailsDialog = ({ id }: { id: string }) => {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const { deployment, isLoading } = useDeploymentDetails(id)

  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={() =>
        navigate(
          getAppRoute({
            to: APP_ROUTES.DEPLOYMENTS({ projectId: projectId as string }),
            keepSearchParams: true,
          })
        )
      }
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
      >
        {deployment ? (
          <DeploymentDetailsDialogContent deployment={deployment} />
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}

const DeploymentDetailsDialogContent = ({
  deployment,
}: {
  deployment: DeploymentDetails
}) => {
  const [isEditing, setIsEditing] = useState(false)
  const { updateDeployment, isLoading, error } = useUpdateDeployment(
    deployment?.id
  )

  useEffect(() => {
    // Reset to view mode when a new deployment is selected
    setIsEditing(false)
  }, [deployment?.id])

  return (
    <>
      {!isEditing ? (
        <DeploymentDetailsInfo
          deployment={deployment}
          title={translate(STRING.DIALOG_DEPLOYMENT_DETAILS)}
          onEditClick={() => setIsEditing(true)}
        />
      ) : (
        <DeploymentDetailsForm
          deployment={deployment}
          serverError={error}
          isLoading={isLoading}
          startValid
          title={translate(STRING.DIALOG_EDIT_DEPLOYMENT)}
          onCancelClick={() => setIsEditing(false)}
          onSubmit={(data) => {
            updateDeployment(data)
          }}
        />
      )}
    </>
  )
}
