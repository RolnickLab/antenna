import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { BasicTableCell } from '../basic-table-cell/basic-table-cell'

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
