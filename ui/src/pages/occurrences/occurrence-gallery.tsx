import { Gallery } from 'components/gallery/gallery'
import { Occurrence } from 'data-services/models/occurrence'
import { useMemo } from 'react'
import { getRoute } from 'utils/getRoute'

export const OccurrenceGallery = ({
  occurrences = [],
  isLoading,
}: {
  occurrences?: Occurrence[]
  isLoading: boolean
}) => {
  const items = useMemo(
    () =>
      occurrences.map((o) => ({
        id: o.id,
        image: o.images[0],
        subTitle: `(${o.determinationScore})`,
        title: o.determinationLabel,
        to: getRoute({ collection: 'occurrences', itemId: o.id }),
      })),
    [occurrences]
  )

  return <Gallery items={items} isLoading={isLoading} />
}
