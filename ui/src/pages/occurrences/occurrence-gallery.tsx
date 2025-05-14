import { Gallery } from 'components/gallery/gallery'
import { Occurrence } from 'data-services/models/occurrence'
import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'

export const OccurrenceGallery = ({
  error,
  isLoading,
  occurrences = [],
}: {
  error?: any
  isLoading: boolean
  occurrences?: Occurrence[]
}) => {
  const { projectId } = useParams()

  const items = useMemo(
    () =>
      occurrences.map((o) => ({
        id: o.id,
        image: o.images[0],
        title: `${o.determinationTaxon.name} (${o.determinationScore})`,
        to: getAppRoute({
          to: APP_ROUTES.OCCURRENCE_DETAILS({
            projectId: projectId as string,
            occurrenceId: o.id,
          }),
          keepSearchParams: true,
        }),
      })),
    [occurrences, projectId]
  )

  return <Gallery error={error} isLoading={isLoading} items={items} />
}
