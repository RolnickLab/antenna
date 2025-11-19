import { DatePicker } from 'design-system/components/select/date-picker'
import { FilterProps } from './types'

export const DateFilter = ({ error, onAdd, onClear, value }: FilterProps) => (
  <DatePicker
    error={error}
    value={value}
    onValueChange={(date) => {
      if (date) {
        onAdd(date)
      } else {
        onClear()
      }
    }}
  />
)
