const OPTIONS: Intl.DateTimeFormatOptions = {
  hour: '2-digit',
  minute: '2-digit',
}

export const getFormatedTimeString = ({
  date,
  locale,
}: {
  date: Date
  locale?: string
}) => date.toLocaleTimeString(locale, OPTIONS)
