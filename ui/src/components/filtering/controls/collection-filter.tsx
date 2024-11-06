import { useCollections } from 'data-services/hooks/collections/useCollections'
import { Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { useFilters } from 'utils/useFilters'

const FILTER_FIELD = 'collection'

export const CollectionFilter = () => {
  const { filters, addFilter } = useFilters()
  const { projectId } = useParams()
  const { collections = [], isLoading } = useCollections(
    {
      projectId: projectId as string,
    },
    0
  )

  const value = filters.find((filter) => filter.field === FILTER_FIELD)?.value

  return (
    <Select.Root
      disabled={isLoading}
      value={value ?? ''}
      onValueChange={(value) => addFilter(FILTER_FIELD, value)}
    >
      <Select.Trigger>
        <Select.Value placeholder="All collections" />
      </Select.Trigger>
      <Select.Content avoidCollisions={false} className="max-h-72">
        {collections.map((c) => (
          <Select.Item key={c.id} value={c.id}>
            {c.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
