import { TimelineTick } from 'data-services/models/timeline-tick'

export const findClosestCaptureId = ({
  maxDate,
  minDate,
  snapToDetections,
  targetDate,
  timeline,
}: {
  maxDate?: Date
  minDate?: Date
  snapToDetections?: boolean
  targetDate: Date
  timeline: TimelineTick[]
}) => {
  let closestCaptureId: string | undefined
  let smallestDifference = Infinity

  timeline.forEach((timelineTick) => {
    if (!timelineTick.representativeCaptureId) {
      return
    }

    if (snapToDetections && !timelineTick.numDetections) {
      return
    }

    if (minDate && timelineTick.startDate <= minDate) {
      return
    }

    if (maxDate && timelineTick.endDate >= maxDate) {
      return
    }

    const difference = Math.abs(
      timelineTick.startDate.getTime() - targetDate.getTime()
    )

    if (difference < smallestDifference) {
      smallestDifference = difference
      closestCaptureId = timelineTick.representativeCaptureId
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
