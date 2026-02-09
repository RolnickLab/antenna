import { useCollections } from 'data-services/hooks/collections/useCollections'
import { Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { FilterProps } from './types'

export const CollectionFilter = ({ value, onAdd }: FilterProps) => {
  const { projectId } = useParams()
  const { collections = [], isLoading } = useCollections({
    projectId: projectId as string,
  })

  return (
    <Select.Root
      disabled={collections.length === 0}
      value={value ?? ''}
      onValueChange={onAdd}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder="All capture sets" />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {collections.map((c) => (
          <Select.Item key={c.id} value={c.id}>
            {c.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
