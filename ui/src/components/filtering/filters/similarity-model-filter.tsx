import { API_ROUTES } from 'data-services/constants'
import { useEntities } from 'data-services/hooks/entities/useEntities'
import { useParams } from 'react-router-dom'
import { FilterProps } from './types'

export const SimilarityModelFilter = ({ value }: FilterProps) => {
  const { projectId } = useParams()
  const { entities = [] } = useEntities(API_ROUTES.OCCURRENCE_ALGORITHMS, {
    projectId: projectId as string,
  })
  const name = entities.find((entity) => entity.id === value)?.name

  return (
    <div className="pt-0.5">
      <span className="text-muted-foreground">{name ?? `#${value}`}</span>
    </div>
  )
}
