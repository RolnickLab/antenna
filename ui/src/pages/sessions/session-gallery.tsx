import { Gallery } from 'components/gallery/gallery'
import { Session } from 'data-services/models/session'
import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { getAppRoute } from 'utils/getAppRoute'

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
        to: getAppRoute({
          projectId: projectId as string,
          collection: 'sessions',
          itemId: s.id,
        }),
      })),
    [sessions, projectId]
  )

  return <Gallery items={items} isLoading={isLoading} />
}
