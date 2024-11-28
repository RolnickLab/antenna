import { useAlgorithms } from 'data-services/hooks/algorithm/useAlgorithms'
import { Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { FilterProps } from './types'

export const AlgorithmFilter = ({
  value,
  onAdd,
  placeholder = 'All algorithms',
}: FilterProps & { placeholder?: string }) => {
  const { projectId } = useParams()
  const { algorithms = [], isLoading } = useAlgorithms({
    projectId: projectId as string,
  })

  return (
    <Select.Root
      disabled={algorithms.length === 0}
      value={value ?? ''}
      onValueChange={onAdd}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder={placeholder} />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {algorithms.map((a) => (
          <Select.Item key={a.id} value={a.id}>
            {a.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}

export const NotAlgorithmFilter = (props: FilterProps) => (
  <AlgorithmFilter {...props} placeholder="No algorithms" />
)
