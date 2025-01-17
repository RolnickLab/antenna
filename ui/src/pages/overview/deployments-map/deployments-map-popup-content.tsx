import { Deployment } from 'data-services/models/deployment'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const DeploymentsMapPopupContent = ({
  deployment,
}: {
  deployment: Deployment
}) => {
  const { projectId } = useParams()

  return (
    <InfoBlock
      fields={[
        {
          label: translate(STRING.FIELD_LABEL_DEPLOYMENT),
          value: deployment.name,
          to: APP_ROUTES.DEPLOYMENT_DETAILS({
            projectId: projectId as string,
            deploymentId: deployment.id,
          }),
        },
        {
          label: translate(STRING.FIELD_LABEL_SESSIONS),
          value: deployment.numEvents,
        },
      ]}
    />
  )
}
