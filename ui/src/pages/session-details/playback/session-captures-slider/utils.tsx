import { TimelineTick } from 'data-services/models/timeline-tick'

export const findClosestCaptureId = (
  timeline: TimelineTick[],
  targetDate: Date
) => {
  let closestCaptureId: string | undefined
  let smallestDifference = Infinity

  timeline.forEach((timelineTick) => {
    const tickDate = timelineTick.startDate
    const difference = Math.abs(tickDate.getTime() - targetDate.getTime())

    if (timelineTick.firstCaptureId && difference < smallestDifference) {
      smallestDifference = difference
      closestCaptureId = timelineTick.firstCaptureId
    }
  })

  return closestCaptureId
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
