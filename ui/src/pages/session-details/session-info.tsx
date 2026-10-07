import { CopyLinkButton } from 'components/copy-link-button/copy-link-button'
import { SessionDetails } from 'data-services/models/session-details'
import { InfoBlock, InfoBlockField } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

export const SessionInfo = ({ session }: { session: SessionDetails }) => {
  const { projectId } = useParams()

  // The id sits in the "Session #" row above, beside the copy-link button.
  const fields = [
    {
      label: translate(STRING.FIELD_LABEL_DEPLOYMENT),
      value: session.deploymentLabel,
      to: APP_ROUTES.DEPLOYMENT_DETAILS({
        projectId: projectId as string,
        deploymentId: session.deploymentId,
      }),
    },
    {
      label: translate(STRING.FIELD_LABEL_DATE),
      value: session.datespanLabel,
    },
    {
      label: translate(STRING.FIELD_LABEL_TIME),
      value: session.timespanLabel,
    },
    {
      label: translate(STRING.FIELD_LABEL_DURATION),
      value: session.durationLabel,
    },
    {
      label: translate(STRING.FIELD_LABEL_CAPTURES),
      value: session.numImages,
    },
    {
      label: translate(STRING.FIELD_LABEL_OCCURRENCES),
      value: session.numOccurrences,
      to: getAppRoute({
        to: APP_ROUTES.OCCURRENCES({ projectId: projectId as string }),
        filters: { event: session.id },
      }),
    },
    ...(session.numTaxa !== undefined
      ? [
          {
            label: translate(STRING.FIELD_LABEL_TAXA),
            value: session.numTaxa,
            to: getAppRoute({
              to: APP_ROUTES.TAXA({ projectId: projectId as string }),
              filters: { event: session.id },
            }),
          },
        ]
      : []),
  ]

  return (
    <div className="grid gap-6">
      <InfoBlockField
        label={translate(STRING.FIELD_LABEL_SESSION_NUMBER, {
          id: session.id,
        })}
      >
        <CopyLinkButton value={window.location.href} />
      </InfoBlockField>
      <InfoBlock fields={fields} />
    </div>
  )
}
