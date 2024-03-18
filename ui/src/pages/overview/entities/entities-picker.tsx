import { useEntities } from 'data-services/hooks/entities/useEntities'
import { Select } from 'design-system/components/select/select'
import { useParams } from 'react-router-dom'

export const EntitiesPicker = ({
  collection,
  value,
  onValueChange,
}: {
  collection: string
  value?: string
  onValueChange: (value?: string) => void
}) => {
  const { projectId } = useParams()
  const { entities = [], isLoading } = useEntities(collection, {
    projectId: projectId as string,
  })
  const hasValue = entities.some((e) => e.id === value)

  return (
    <Select
      loading={isLoading}
      options={entities.map((e) => ({
        value: e.id,
        label: e.name,
      }))}
      showClear={false}
      value={hasValue ? value : undefined}
      onValueChange={onValueChange}
    />
  )
}
