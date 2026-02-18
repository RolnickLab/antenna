import { Gallery } from 'components/gallery/gallery'
import { Project } from 'data-services/models/project'
import { Card, CardSize } from 'design-system/components/card/card'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'

export const ProjectGallery = ({
  error,
  isLoading,
  projects = [],
}: {
  error?: any
  isLoading: boolean
  projects?: Project[]
}) => {
  const items = useMemo(
    () =>
      projects.map((p) => ({
        id: p.id,
        image: p.image
          ? {
              src: p.image,
            }
          : undefined,
        label: p.isDraft ? 'Draft' : undefined,
        subTitle: p.description,
        title: p.name,
        to: APP_ROUTES.PROJECT_DETAILS({ projectId: p.id }),
      })),
    [projects]
  )

  return (
    <Gallery
      error={error}
      cardSize={CardSize.Large}
      isLoading={isLoading}
      items={items}
      renderItem={(item) => (
        <Link key={item.id} to={item.to as string}>
          <Card
            key={item.id}
            image={item.image}
            label={item.label}
            size={CardSize.Large}
            subTitle={item.subTitle}
            title={item.title}
          />
        </Link>
      )}
      style={{ gridTemplateColumns: '1fr 1fr 1fr' }}
    />
  )
}
