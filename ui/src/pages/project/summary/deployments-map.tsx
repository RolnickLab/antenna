import { FormMessage } from 'components/form/layout/layout'
import { MultiMarkerMap } from 'components/map/multi-marker-map/multi-marker-map'
import { MarkerPosition } from 'components/map/types'
import { Deployment } from 'data-services/models/deployment'
import { ChevronRightIcon } from 'lucide-react'
import { InfoBlock } from 'nova-ui-kit'
import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const DeploymentsMap = ({
  deployments,
  projectId,
}: {
  deployments: Deployment[]
  projectId: string
}) => {
  const markers = useMemo(
    () =>
      deployments
        .filter((deployment) => deployment.latitude || deployment.longitude)
        .map((deployment) => ({
          position: new MarkerPosition(
            deployment.latitude,
            deployment.longitude
          ),
          popupContent: <DeploymentsMapPopupContent deployment={deployment} />,
        })),
    [deployments]
  )

  const showTip =
    markers.length === 0 &&
    deployments.some((deployment) => deployment.canUpdate)

  return (
    <div className="flex flex-col gap-4">
      {showTip ? (
        <FormMessage
          className="flex justify-between gap-4"
          message={translate(STRING.MESSAGE_CONFIGURE_LOCATION)}
          theme="success"
          withIcon
        >
          <Link
            className="shrink-0 font-bold"
            to={APP_ROUTES.DEPLOYMENTS({
              projectId: projectId as string,
            })}
          >
            <span>{translate(STRING.NAV_ITEM_DEPLOYMENTS)}</span>
            <ChevronRightIcon className="inline w-4 h-4 ml-2" />
          </Link>
        </FormMessage>
      ) : null}
      <MultiMarkerMap markers={markers} />
    </div>
  )
}

const DeploymentsMapPopupContent = ({
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
