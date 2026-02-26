import { useEntities } from 'data-services/hooks/entities/useEntities'
import { Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

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

  return (
    <Select.Root
      disabled={entities.length === 0}
      onValueChange={onValueChange}
      value={entities.some((e) => e.id === value) ? value : ''}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {entities.map((e) => (
          <Select.Item key={e.id} value={e.id}>
            {e.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
