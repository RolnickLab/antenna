import { usePipelines } from 'data-services/hooks/pipelines/usePipelines'
import { Select } from 'design-system/components/select/select'
import { useParams } from 'react-router-dom'

export const PipelinesPicker = ({
  value,
  onValueChange,
}: {
  value?: string
  onValueChange: (value?: string) => void
}) => {
  const { projectId } = useParams()
  const { pipelines = [], isLoading } = usePipelines({
    projectId: projectId as string,
  })

  return (
    <Select
      loading={isLoading}
      onValueChange={onValueChange}
      options={pipelines.map((p) => ({
        value: p.id,
        label: p.name,
      }))}
      showClear={false}
      value={value}
    />
  )
}
