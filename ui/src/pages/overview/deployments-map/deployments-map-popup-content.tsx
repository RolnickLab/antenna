import { Deployment } from 'data-services/models/deployment'
import { Link } from 'react-router-dom'
import { getRoute } from 'utils/getRoute'
import { STRING, translate } from 'utils/language'

export const DeploymentsMapPopupContent = ({
  deployment,
}: {
  deployment: Deployment
}) => (
  <>
    <p>
      <Link to={getRoute({ collection: 'deployments', itemId: deployment.id })}>
        <span>{deployment.name}</span>
      </Link>
    </p>
    <p>
      <span>
        {translate(STRING.DETAILS_LABEL_SESSIONS)}: {deployment.numEvents}
      </span>
      <br />
      <span>
        {translate(STRING.TABLE_COLUMN_CAPTURES)}: {deployment.numImages}
      </span>
      <br />
      <span>
        {translate(STRING.DETAILS_LABEL_DETECTIONS)}: {deployment.numDetections}
      </span>
    </p>
  </>
)
