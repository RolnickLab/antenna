import { getFormatedDateString } from '../getFormatedDateString/getFormatedDateString'
import { getFormatedTimeString } from '../getFormatedTimeString/getFormatedTimeString'

export const getFormatedDateTimeString = ({
  date,
  locale,
  options = {},
}: {
  date: Date
  locale?: string
  options?: {
    second?: boolean
  }
}) => {
  const dateString = getFormatedDateString({ date, locale })
  const timeString = getFormatedTimeString({ date, locale, options })

  return `${dateString} ${timeString}`
}
