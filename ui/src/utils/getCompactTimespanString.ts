export const getCompactTimespanString = ({
  date1,
  date2,
  locale,
}: {
  date1: Date
  date2: Date
  locale?: string
}) => {
  const day1 = date1.toLocaleDateString(locale, { day: '2-digit' })
  const day2 = date2.toLocaleDateString(locale, { day: '2-digit' })
  const month1 = date1.toLocaleDateString(locale, { month: 'short' })
  const month2 = date2.toLocaleDateString(locale, { month: 'short' })
  const year1 = date1.toLocaleDateString(locale, { year: 'numeric' })
  const year2 = date2.toLocaleDateString(locale, { year: 'numeric' })

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
