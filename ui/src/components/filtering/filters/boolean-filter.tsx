import { Select } from 'nova-ui-kit'
import { booleanToString, stringToBoolean } from '../utils'
import { FilterProps } from './types'

const OPTIONS = [
  { value: true, label: 'Yes' },
  { value: false, label: 'No' },
]

export const BooleanFilter = ({
  value: string,
  onAdd,
  onClear,
}: FilterProps) => {
  const value = stringToBoolean(string) ?? false

  return (
    <Select.Root
      value={booleanToString(value)}
      onValueChange={(value) => {
        if (stringToBoolean(value)) {
          onAdd(value)
        } else {
          onClear()
        }
      }}
    >
      <Select.Trigger>
        <Select.Value placeholder="Select a value" />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {OPTIONS.map((option) => (
          <Select.Item
            key={booleanToString(option.value)}
            value={booleanToString(option.value)}
          >
            {option.label}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
