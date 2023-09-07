import { Deployment } from 'data-services/models/deployment'
import { Link, useParams } from 'react-router-dom'
import { getAppRoute } from 'utils/getAppRoute'
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
          to={getAppRoute({
            projectId: projectId as string,
            collection: 'deployments',
            itemId: deployment.id,
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
