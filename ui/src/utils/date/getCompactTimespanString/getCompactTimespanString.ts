const OPTIONS: Intl.DateTimeFormatOptions = {
  hour: '2-digit',
  minute: '2-digit',
}

export const getCompactTimespanString = ({
  date1,
  date2,
  locale,
}: {
  date1: Date
  date2: Date
  locale?: string
}) => {
  const time1 = date1.toLocaleTimeString(locale, OPTIONS)
  const time2 = date2.toLocaleTimeString(locale, OPTIONS)

  return `${time1} - ${time2}`
}
