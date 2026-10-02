import { useAlgorithms } from 'data-services/hooks/algorithm/useAlgorithms'
import { Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

// Jobs identify an algorithm by key rather than id, so this picks the key. Only heads a
// service will accept are offered.
export const TrainableAlgorithmPicker = ({
  value,
  onValueChange,
}: {
  value?: string
  onValueChange: (value?: string) => void
}) => {
  const { projectId } = useParams()
  const { algorithms = [], isLoading } = useAlgorithms({
    projectId: projectId as string,
    filters: [{ field: 'trainable', value: 'true' }],
  })

  return (
    <Select.Root
      key={value}
      disabled={isLoading || algorithms.length === 0}
      onValueChange={onValueChange}
      value={algorithms.some((a) => a.key === value) ? value : ''}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {algorithms.map((algorithm) => (
          <Select.Item key={algorithm.id} value={algorithm.key}>
            {algorithm.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
