import { Gallery } from 'components/gallery/gallery'
import { Species } from 'data-services/models/species'
import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'

export const SpeciesGallery = ({
  error,
  isLoading,
  species = [],
}: {
  error?: any
  isLoading: boolean
  species?: Species[]
}) => {
  const { projectId } = useParams()

  const items = useMemo(
    () =>
      species.map((s) => ({
        id: s.id,
        image: s.coverImage ? { src: s.coverImage.url } : undefined,
        title: s.name,
        to: getAppRoute({
          to: APP_ROUTES.TAXON_DETAILS({
            projectId: projectId as string,
            taxonId: s.id,
          }),
          keepSearchParams: true,
        }),
      })),
    [species]
  )

  return <Gallery error={error} isLoading={isLoading} items={items} />
}
