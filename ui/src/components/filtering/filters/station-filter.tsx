import { useDeployments } from 'data-services/hooks/deployments/useDeployments'
import { Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { FilterProps } from './types'

export const StationFilter = ({ value, onAdd }: FilterProps) => {
  const { projectId } = useParams()
  const { deployments = [], isLoading } = useDeployments({
    projectId: projectId as string,
  })

  return (
    <Select.Root
      disabled={deployments.length === 0}
      value={value ?? ''}
      onValueChange={onAdd}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder="All stations" />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {deployments.map((d) => (
          <Select.Item key={d.id} value={d.id}>
            {d.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
