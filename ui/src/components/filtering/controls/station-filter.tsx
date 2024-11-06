import { useDeployments } from 'data-services/hooks/deployments/useDeployments'
import { Select } from 'nova-ui-kit'
import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useFilters } from 'utils/useFilters'

const FILTER_FIELD = 'deployment'

export const StationFilter = () => {
  const { filters, addFilter } = useFilters()
  const { projectId } = useParams()
  const { deployments = [], isLoading } = useDeployments({
    projectId: projectId as string,
  })

  const value = filters.find((filter) => filter.field === FILTER_FIELD)?.value

  return (
    <Select.Root
      disabled={isLoading}
      value={value ?? ''}
      onValueChange={(value) => addFilter(FILTER_FIELD, value)}
    >
      <Select.Trigger>
        <Select.Value placeholder="All stations" />
      </Select.Trigger>
      <Select.Content avoidCollisions={false} className="max-h-72">
        {deployments.map((d) => (
          <Select.Item key={d.id} value={d.id}>
            {d.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
