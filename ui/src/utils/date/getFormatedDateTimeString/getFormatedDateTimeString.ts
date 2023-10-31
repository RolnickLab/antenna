import { getFormatedDateString } from '../getFormatedDateString/getFormatedDateString'
import { getFormatedTimeString } from '../getFormatedTimeString/getFormatedTimeString'

export const getFormatedDateTimeString = ({
  date,
  locale,
}: {
  date: Date
  locale?: string
}) => {
  const dateString = getFormatedDateString({ date, locale })
  const timeString = getFormatedTimeString({ date, locale })

  return `${dateString} ${timeString}`
}
