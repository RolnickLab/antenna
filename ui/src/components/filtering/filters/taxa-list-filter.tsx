import { TaxaList } from 'data-services/models/taxa-list'
import { Select } from 'nova-ui-kit'
import { FilterProps } from './types'

export const TaxaListFilter = ({ data = [], value, onAdd }: FilterProps) => {
  const taxaLists = data as TaxaList[]

  return (
    <Select.Root
      disabled={taxaLists.length === 0}
      value={value ?? ''}
      onValueChange={onAdd}
    >
      <Select.Trigger>
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
