import { SessionDetails } from 'data-services/models/session-details'
import { InfoBlockField, InfoBlockFieldValue } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

export const SessionStats = ({ session }: { session: SessionDetails }) => {
  const { projectId } = useParams()
  const stats = session.detectionsPerCapture

  if (!stats) {
    return null
  }

  return (
    <InfoBlockField
      label={translate(STRING.FIELD_LABEL_DETECTIONS_PER_CAPTURE)}
    >
      <InfoBlockFieldValue
        value={`${translate(STRING.FIELD_LABEL_MAX)}: ${stats.max}`}
        to={getAppRoute({
          to: APP_ROUTES.SESSION_DETAILS({
            projectId: projectId as string,
            sessionId: session.id,
          }),
          filters: { capture: stats.busiestCaptureId },
        })}
      />
      <InfoBlockFieldValue
        value={`${translate(STRING.FIELD_LABEL_MEDIAN)}: ${stats.median}`}
      />
      <InfoBlockFieldValue
        value={`${translate(STRING.FIELD_LABEL_QUARTILES)}: ${
          stats.quartiles[0]
        } – ${stats.quartiles[1]}`}
      />
    </InfoBlockField>
  )
}
