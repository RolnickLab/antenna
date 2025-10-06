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
        <Select.Value placeholder="Select a pipeline">
          <span>{pipeline?.name}</span>
        </Select.Value>
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {pipelines.map((p) => (
          <Select.Item className="h-auto min-h-12 py-2" key={p.id} value={p.id}>
            <div className="grid gap-1">
              <span className="body-base">{p.name}</span>
              {p.description ? (
                <span className="body-small">{p.description}</span>
              ) : null}
            </div>
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
