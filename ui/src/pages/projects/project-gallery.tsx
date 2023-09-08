import { Gallery } from 'components/gallery/gallery'
import { Project } from 'data-services/models/project'
import { CardSize } from 'design-system/components/card/card'
import { useMemo } from 'react'
import { APP_ROUTES } from 'utils/constants'

export const ProjectGallery = ({
  projects = [],
  isLoading,
}: {
  projects?: Project[]
  isLoading: boolean
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
        title: p.name,
        subTitle: p.description,
        to: APP_ROUTES.PROJECT_DETAILS({ projectId: p.id }),
      })),
    [projects]
  )

  return (
    <Gallery
      cardSize={CardSize.Large}
      isLoading={isLoading}
      items={items}
      style={{ gridTemplateColumns: '1fr 1fr 1fr' }}
    />
  )
}
