import { useCaptureSets } from 'data-services/hooks/capture-sets/useCaptureSets'
import { Select } from 'design-system/components/select/select'
import { useParams } from 'react-router-dom'

export const CaptureSetPicker = ({
  onValueChange,
  showClear,
  value,
}: {
  onValueChange: (value?: string) => void
  showClear?: boolean
  value?: string
}) => {
  const { projectId } = useParams()
  const { captureSets = [], isLoading } = useCaptureSets({
    projectId: projectId as string,
  })

  return (
    <Select
      loading={isLoading}
      onValueChange={onValueChange}
      options={captureSets.map((c) => ({
        value: c.id,
        label: c.name,
      }))}
      showClear={showClear}
      value={value}
    />
  )
}
