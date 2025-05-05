import { AVAILABLE_TAGS } from 'components/taxon-tags/constants'
import { Select } from 'nova-ui-kit'
import { booleanToString, stringToBoolean } from '../utils'
import { FilterProps } from './types'

export const TagFilter = ({ value: string, onAdd }: FilterProps) => {
  const value = stringToBoolean(string)

  return (
    <Select.Root value={booleanToString(value)} onValueChange={onAdd}>
      <Select.Trigger>
        <Select.Value placeholder="Select a value" />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {AVAILABLE_TAGS.map((option) => (
          <Select.Item key={option.value} value={option.value}>
            {option.label}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
