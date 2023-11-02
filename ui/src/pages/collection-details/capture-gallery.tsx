import { Gallery } from 'components/gallery/gallery'
import { Capture } from 'data-services/models/capture'
import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'

export const CaptureGallery = ({
  captures = [],
  isLoading,
}: {
  captures?: Capture[]
  isLoading: boolean
}) => {
  const { projectId } = useParams()

  const items = useMemo(
    () =>
      captures.map((c) => ({
        id: c.id,
        image: { src: c.src },
        title: c.dateTimeLabel,
        to: getAppRoute({
          to: APP_ROUTES.SESSION_DETAILS({
            projectId: projectId as string,
            sessionId: c.sessionId,
          }),
          filters: {
            capture: c.id,
          },
        }),
      })),
    [captures, projectId]
  )

  return <Gallery items={items} isLoading={isLoading} />
}
