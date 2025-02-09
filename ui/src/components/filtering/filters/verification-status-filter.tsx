import { Select } from 'nova-ui-kit'
import { booleanToString, stringToBoolean } from '../utils'
import { FilterProps } from './types'

const OPTIONS = [
  { value: true, label: 'Verified' },
  { value: false, label: 'Not verified' },
]

export const VerificationStatusFilter = ({
  value: string,
  onAdd,
}: FilterProps) => {
  const value = stringToBoolean(string)

  return (
    <Select.Root value={booleanToString(value)} onValueChange={onAdd}>
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
