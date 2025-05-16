import { Gallery } from 'components/gallery/gallery'
import { Occurrence } from 'data-services/models/occurrence'
import { Card } from 'design-system/components/card/card'
import { FeatureControl } from 'pages/occurrence-details/feature-control/feature-control'
import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
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

  return (
    <Gallery
      error={error}
      isLoading={isLoading}
      items={items}
      renderItem={(item) => (
        <div key={item.id} className="relative group">
          <Link className="w-full" id={item.id} to={item.to as string}>
            <Card
              image={item.image}
              subTitle={item.subTitle}
              title={item.title}
            />
          </Link>
          <div className="absolute top-1 right-1 hidden group-hover:block">
            <FeatureControl occurrenceId={item.id} />
          </div>
        </div>
      )}
    />
  )
}
