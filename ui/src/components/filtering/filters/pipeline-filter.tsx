import { usePipelines } from 'data-services/hooks/pipelines/usePipelines'
import { Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { FilterProps } from './types'

export const PipelineFilter = ({ value, onAdd }: FilterProps) => {
  const { projectId } = useParams()
  const { pipelines = [], isLoading } = usePipelines({
    projectId: projectId as string,
  })

  return (
    <Select.Root
      disabled={pipelines.length === 0}
      value={value ?? ''}
      onValueChange={onAdd}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder="All pipelines" />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {pipelines.map((p) => (
          <Select.Item key={p.id} value={p.id}>
            {p.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
