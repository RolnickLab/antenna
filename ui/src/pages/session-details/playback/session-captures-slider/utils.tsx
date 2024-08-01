import { Capture } from 'data-services/models/capture'

export const findClosestCapture = (captures: Capture[], targetDate: Date) => {
  let closestCapture: Capture | undefined
  let smallestDifference = Infinity

  captures.forEach((capture) => {
    const captureDate = capture.date
    const difference = Math.abs(captureDate.getTime() - targetDate.getTime())

    if (difference < smallestDifference) {
      smallestDifference = difference
      closestCapture = capture
    }
  })

  return closestCapture
}

export const dateToValue = ({
  date,
  startDate,
  endDate,
}: {
  date: Date
  startDate: Date
  endDate: Date
}) =>
  ((date.getTime() - startDate.getTime()) /
    (endDate.getTime() - startDate.getTime())) *
  100

export const valueToDate = ({
  value,
  startDate,
  endDate,
}: {
  value: number
  startDate: Date
  endDate: Date
}) =>
  new Date(
    startDate.getTime() +
      ((endDate.getTime() - startDate.getTime()) * value) / 100
  )
