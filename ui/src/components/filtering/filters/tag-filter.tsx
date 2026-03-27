import { Select } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { FilterProps } from './types'

export const TagFilter = ({ data = [], value, onAdd }: FilterProps) => {
  const tags = data as { id: number; name: string }[]

  return (
    <Select.Root
      disabled={tags.length === 0}
      value={value ?? ''}
      onValueChange={onAdd}
    >
      <Select.Trigger>
        <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
      </Select.Trigger>
      <Select.Content>
        {tags.map((option) => (
          <Select.Item key={option.id} value={`${option.id}`}>
            {option.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
