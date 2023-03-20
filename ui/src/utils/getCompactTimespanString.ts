export const getCompactTimespanString = ({
  date1,
  date2,
  locale,
}: {
  date1: Date
  date2: Date
  locale?: string
}) => {
  const options: Intl.DateTimeFormatOptions = {
    hour: '2-digit',
    minute: '2-digit',
  }
  const time1 = date1.toLocaleTimeString(locale, options)
  const time2 = date2.toLocaleTimeString(locale, options)

  return `${time1} - ${time2}`
}
