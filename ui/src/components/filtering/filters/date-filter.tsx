import { DatePicker } from 'nova-ui-kit'
import { FilterProps } from './types'

export const DateFilter = ({ error, onAdd, onClear, value }: FilterProps) => (
  // The marker gives the page room below for the calendar (see app.module.scss).
  <div className="w-full" data-date-filter>
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
  </div>
)
