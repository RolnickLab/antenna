import { Select } from 'nova-ui-kit'
import { FilterProps } from './types'

const OPTIONS = [
  { value: true, label: 'Verified' },
  { value: false, label: 'Not verified' },
]

export const VerificationStatusFilter = ({
  value: string,
  onAdd,
}: FilterProps) => {
  const value = stringToValue(string)

  return (
    <Select.Root value={valueToString(value)} onValueChange={onAdd}>
      <Select.Trigger>
        <Select.Value placeholder="Select a value" />
      </Select.Trigger>
      <Select.Content className="max-h-72">
        {OPTIONS.map((option) => (
          <Select.Item
            key={valueToString(option.value)}
            value={valueToString(option.value)}
          >
            {option.label}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}

// Help functions to handle search param string value conversion (filter values are always strings since defined as search params)
const stringToValue = (string?: string) => {
  switch (string?.toLowerCase()) {
    case 'true':
    case '1':
      return true
    case 'false':
    case '0':
      return false
    default:
      return undefined
  }
}

const valueToString = (value?: boolean) =>
  value !== undefined ? `${value}` : ''
