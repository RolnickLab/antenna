import { Gallery } from 'components/gallery/gallery'
import { Species } from 'data-services/models/species'
import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'

export const SpeciesGallery = ({
  species = [],
  isLoading,
}: {
  species?: Species[]
  isLoading: boolean
}) => {
  const { projectId } = useParams()

  const items = useMemo(
    () =>
      species.map((s) => ({
        id: s.id,
        image: s.images[0],
        title: s.name,
        to: getAppRoute({
          to: APP_ROUTES.SPECIES_DETAILS({
            projectId: projectId as string,
            speciesId: s.id,
          }),
          keepSearchParams: true,
        }),
      })),
    [species]
  )

  return <Gallery items={items} isLoading={isLoading} />
}
