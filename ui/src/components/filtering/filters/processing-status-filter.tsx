import { Select } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { booleanToString, stringToBoolean } from '../utils'
import { FilterProps } from './types'

export const ProcessingStatusFilter = ({ value, onAdd }: FilterProps) => {
  const booleanValue = stringToBoolean(value)
  const options = [
    { value: true, label: translate(STRING.PROCESSED) },
    { value: false, label: translate(STRING.NOT_PROCESSED) },
  ]

  return (
    <Select.Root value={booleanToString(booleanValue)} onValueChange={onAdd}>
      <Select.Trigger>
        <Select.Value placeholder={translate(STRING.SELECT_PLACEHOLDER)} />
      </Select.Trigger>
      <Select.Content>
        {options.map((option) => (
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
