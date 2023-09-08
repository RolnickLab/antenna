import { Deployment } from 'data-services/models/deployment'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const DeploymentsMapPopupContent = ({
  deployment,
}: {
  deployment: Deployment
}) => {
  const { projectId } = useParams()

  return (
    <>
      <p>
        <Link
          to={APP_ROUTES.DEPLOYMENT_DETAILS({
            projectId: projectId as string,
            deploymentId: deployment.id,
          })}
        >
          <span>{deployment.name}</span>
        </Link>
      </p>
      <p>
        <span>
          {translate(STRING.FIELD_LABEL_SESSIONS)}: {deployment.numEvents}
        </span>
        <br />
        <span>
          {translate(STRING.FIELD_LABEL_CAPTURES)}: {deployment.numImages}
        </span>
        <br />
        <span>
          {translate(STRING.FIELD_LABEL_OCCURRENCES)}:{' '}
          {deployment.numOccurrences}
        </span>
      </p>
    </>
  )
}
