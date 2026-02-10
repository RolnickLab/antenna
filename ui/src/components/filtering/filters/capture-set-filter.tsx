import { useCaptureSets } from 'data-services/hooks/capture-sets/useCaptureSets'
import { Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { FilterProps } from './types'

export const CaptureSetFilter = ({ value, onAdd }: FilterProps) => {
  const { projectId } = useParams()
  const { captureSets = [], isLoading } = useCaptureSets({
    projectId: projectId as string,
  })

  return (
    <Select.Root
      disabled={captureSets.length === 0}
      value={value ?? ''}
      onValueChange={onAdd}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder="All capture sets" />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {captureSets.map((c) => (
          <Select.Item key={c.id} value={c.id}>
            {c.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
