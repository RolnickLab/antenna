import { Select } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { booleanToString, stringToBoolean } from '../utils'
import { FilterProps } from './types'

const OPTIONS = [
  { value: true, label: 'Verified by me' },
  { value: false, label: 'Not verified by me' },
]

export const VerifiedByFilter = ({ onAdd, value: string }: FilterProps) => {
  const value = stringToBoolean(string)

  return (
    <Select.Root value={booleanToString(value)} onValueChange={onAdd}>
      <Select.Trigger>
        <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
      </Select.Trigger>
      <Select.Content>
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
