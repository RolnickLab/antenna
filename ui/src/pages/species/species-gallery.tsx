import { Gallery } from 'components/gallery/gallery'
import { Species } from 'data-services/models/species'
import { useMemo } from 'react'
import { getRoute } from 'utils/getRoute'

export const SpeciesGallery = ({
  species = [],
  isLoading,
}: {
  species?: Species[]
  isLoading: boolean
}) => {
  const items = useMemo(
    () =>
      species.map((s) => ({
        id: s.id,
        image: s.images[0],
        title: s.name,
        to: getRoute({
          collection: 'species',
          itemId: s.id,
          keepSearchParams: true,
        }),
      })),
    [species]
  )

  return <Gallery items={items} isLoading={isLoading} />
}
