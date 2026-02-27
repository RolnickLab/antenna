import { usePipelines } from 'data-services/hooks/pipelines/usePipelines'
import { Select } from 'nova-ui-kit'
import { useMemo } from 'react'
import { useParams } from 'react-router-dom'

// TODO: Define these options backend side?
const DEFAULT_PIPELINE_IDS = [
  '3', // Quebec & Vermont moths
  '2', // UK & Denmark moths
  '1', // Panama moths
  '4', // World moths
]

export const PipelinesSelect = ({
  onPipelineChange,
  pipeline,
}: {
  onPipelineChange: (pipeline?: { id: string; name: string }) => void
  pipeline?: { id: string; name: string }
}) => {
  const { projectId } = useParams()
  const { pipelines: _pipelines = [], isLoading } = usePipelines({
    projectId,
  })

  const pipelines = useMemo(() => {
    if (projectId) {
      return _pipelines
    }

    // In the case of new projects, return a limited and sorted list of pipelines to present as default options
    return _pipelines
      .filter((pipeline) => DEFAULT_PIPELINE_IDS.includes(pipeline.id))
      .sort(
        (p1, p2) =>
          DEFAULT_PIPELINE_IDS.indexOf(p1.id) -
          DEFAULT_PIPELINE_IDS.indexOf(p2.id)
      )
  }, [_pipelines, projectId])

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
      <Select.Content>
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
