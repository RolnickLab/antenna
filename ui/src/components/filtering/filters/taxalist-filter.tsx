import { useTaxaLists } from 'data-services/hooks/taxalists/useTaxaLists'
import { Select } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { FilterProps } from './types'

export const TaxaListFilter = ({ value, onAdd }: FilterProps) => {
  const { projectId } = useParams()

  // Fetch TaxaLists filtered by projectId
  const { taxaLists = [], isLoading } = useTaxaLists({
    projectId: projectId as string,
  })

  return (
    <Select.Root
      disabled={taxaLists.length === 0}
      value={value ?? ''}
      onValueChange={onAdd}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value placeholder="All taxa lists" />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {taxaLists.map((list) => (
          <Select.Item key={list.id} value={list.id}>
            {list.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
