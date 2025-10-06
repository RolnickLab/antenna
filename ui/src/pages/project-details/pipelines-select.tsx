import { usePipelines } from 'data-services/hooks/pipelines/usePipelines'
import { Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'

export const PipelinesSelect = ({
  onPipelineChange,
  pipeline,
}: {
  onPipelineChange: (pipeline?: { id: string; name: string }) => void
  pipeline?: { id: string; name: string }
}) => {
  const { projectId } = useParams()
  const { pipelines = [], isLoading } = usePipelines({
    projectId: projectId as string,
  })

  return (
    <Select.Root
      disabled={pipelines.length === 0}
      onValueChange={(value) => {
        const pipeline = pipelines.find((p) => p.id === value)
        onPipelineChange(pipeline)
      }}
      value={pipeline?.id ?? ''}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder="Select a pipeline" />
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
