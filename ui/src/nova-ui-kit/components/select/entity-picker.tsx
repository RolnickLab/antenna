import { useEntities } from 'data-services/hooks/entities/useEntities'
import { FetchParams } from 'data-services/types'
import { Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

// TODO: Move to src/components, this is not a design system component
export const EntityPicker = ({
  collection,
  filters,
  value: _value,
  onValueChange,
}: {
  collection: string
  filters?: FetchParams['filters']
  value?: string
  onValueChange: (value?: string) => void
}) => {
  const { projectId } = useParams()
  const { entities = [], isLoading } = useEntities(collection, {
    projectId: projectId as string,
    filters,
  })
  const value = entities.some((e) => e.id === _value) ? _value : ''

  return (
    <Select.Root
      key={value}
      disabled={isLoading || entities.length === 0}
      onValueChange={onValueChange}
      value={value}
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
