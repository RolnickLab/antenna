import { Gallery } from 'components/gallery/gallery'
import { Occurrence } from 'data-services/models/occurrence'
import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'

export const OccurrenceGallery = ({
  occurrences = [],
  isLoading,
}: {
  occurrences?: Occurrence[]
  isLoading: boolean
}) => {
  const { projectId } = useParams()

  const items = useMemo(
    () =>
      occurrences.map((o) => ({
        id: o.id,
        image: o.images[0],
        subTitle: `(${o.determinationScore})`,
        title: o.determinationLabel,
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

  return <Gallery items={items} isLoading={isLoading} />
}
