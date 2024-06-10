const OPTIONS: Intl.DateTimeFormatOptions = {
  hour: '2-digit',
  minute: '2-digit',
}

export const getFormatedTimeString = ({
  date,
  locale,
  options = {},
}: {
  date: Date
  locale?: string
  options?: {
    second?: boolean
  }
}) =>
  date.toLocaleTimeString(locale, {
    ...OPTIONS,
    ...(options.second ? { second: '2-digit' } : {}),
  })
