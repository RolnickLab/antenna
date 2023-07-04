const DAY_OPTIONS: Intl.DateTimeFormatOptions = { day: '2-digit' }
const MONTH_OPTIONS: Intl.DateTimeFormatOptions = { month: 'short' }
const YEAR_OPTIONS: Intl.DateTimeFormatOptions = { year: 'numeric' }

export const getCompactDatespanString = ({
  date1,
  date2,
  locale,
}: {
  date1: Date
  date2: Date
  locale?: string
}) => {
  const day1 = date1.toLocaleDateString(locale, DAY_OPTIONS)
  const day2 = date2.toLocaleDateString(locale, DAY_OPTIONS)
  const month1 = date1.toLocaleDateString(locale, MONTH_OPTIONS)
  const month2 = date2.toLocaleDateString(locale, MONTH_OPTIONS)
  const year1 = date1.toLocaleDateString(locale, YEAR_OPTIONS)
  const year2 = date2.toLocaleDateString(locale, YEAR_OPTIONS)

  if (year1 === year2) {
    if (month1 === month2) {
      if (day1 === day2) {
        // Same day, same month, same year
        return `${month1} ${day1}, ${year1}`
      }

      // Same same month, same year
      return `${month1} ${day1}-${day2}, ${year1}`
    }

    // Same year
    return `${month1} ${day1} - ${month2} ${day2}, ${year1}`
  }

  // Different day, month and year
  return `${month1} ${day1}, ${year1} - ${month2} ${day2}, ${year2}`
}
