import { BasicTableCell } from 'nova-ui-kit'
import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'

interface DateTableCellProps {
  date?: Date
}

export const DateTableCell = ({ date }: DateTableCellProps) => {
  if (!date) {
    return <BasicTableCell />
  }

  return (
    <BasicTableCell
      value={getFormatedDateString({ date })}
      details={[getFormatedTimeString({ date })]}
    />
  )
}
