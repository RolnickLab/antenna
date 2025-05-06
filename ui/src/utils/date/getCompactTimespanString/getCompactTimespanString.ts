import { getFormatedTimeString } from '../getFormatedTimeString/getFormatedTimeString'

export const getCompactTimespanString = ({
  date1,
  date2,
  locale,
  options = {},
}: {
  date1: Date
  date2: Date
  locale?: string
  options?: {
    second?: boolean
  }
}) => {
  const time1 = getFormatedTimeString({ date: date1, locale, options })
  const time2 = getFormatedTimeString({ date: date2, locale, options })

  if (time1 === time2) {
    return time1
  }

  return `${time1} - ${time2}`
}
