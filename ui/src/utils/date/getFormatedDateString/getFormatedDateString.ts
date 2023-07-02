const OPTIONS: Intl.DateTimeFormatOptions = {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
}

export const getFormatedDateString = ({
  date,
  locale,
}: {
  date: Date
  locale?: string
}) => date.toLocaleDateString(locale, OPTIONS)
