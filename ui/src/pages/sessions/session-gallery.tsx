import { Gallery } from 'components/gallery/gallery'
import { Session } from 'data-services/models/session'

import { useMemo } from 'react'
import { getRoute } from 'utils/getRoute'

export const SessionGallery = ({
  sessions = [],
  isLoading,
}: {
  sessions?: Session[]
  isLoading: boolean
}) => {
  const items = useMemo(
    () =>
      sessions.map((s) => ({
        id: s.id,
        image: s.exampleCaptures?.[0],
        title: s.label,
        to: getRoute({ collection: 'sessions', itemId: s.id }),
      })),
    [sessions]
  )

  return <Gallery items={items} isLoading={isLoading} />
}