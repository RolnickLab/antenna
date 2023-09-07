import { Gallery } from 'components/gallery/gallery'
import { Session } from 'data-services/models/session'
import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'

export const SessionGallery = ({
  sessions = [],
  isLoading,
}: {
  sessions?: Session[]
  isLoading: boolean
}) => {
  const { projectId } = useParams()

  const items = useMemo(
    () =>
      sessions.map((s) => ({
        id: s.id,
        image: s.exampleCaptures?.[0],
        title: s.label,
        to: APP_ROUTES.SESSION_DETAILS({
          projectId: projectId as string,
          sessionId: s.id,
        }),
      })),
    [sessions, projectId]
  )

  return <Gallery items={items} isLoading={isLoading} />
}
