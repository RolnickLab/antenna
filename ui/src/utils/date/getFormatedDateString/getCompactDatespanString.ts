export const getFormatedDateString = ({
  date,
  locale,
}: {
  date: Date
  locale?: string
}) => {
  const dateString = date.toLocaleDateString(locale, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })

  const timeString = date.toLocaleTimeString(locale, {
    hour: '2-digit',
    minute: '2-digit',
  })

  return `${dateString} ${timeString}`
}
