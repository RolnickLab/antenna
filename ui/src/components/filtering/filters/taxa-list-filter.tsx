import { TaxaList } from 'data-services/models/taxa-list'
import { Select } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
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
        <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
      </Select.Trigger>
      <Select.Content>
        {taxaLists.map((list) => (
          <Select.Item key={list.id} value={list.id}>
            {list.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
