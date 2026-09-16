import { Select } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { booleanToString, stringToBoolean } from '../utils'
import { FilterProps } from './types'

export const GroupingStatusFilter = ({ value: string, onAdd }: FilterProps) => {
  const value = stringToBoolean(string)
  const options = [
    { value: true, label: translate(STRING.TRACK_GROUPING_FILTER_YES) },
    { value: false, label: translate(STRING.TRACK_GROUPING_FILTER_NO) },
  ]

  return (
    <Select.Root value={booleanToString(value)} onValueChange={onAdd}>
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
