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

// The timeline resolves to one tick per minute, so a shorter session collapses
// into a single tick with nothing to scrub. An unknown span stays visible.
const MIN_TIMELINE_SPAN_MS = 60 * 1000

export const showSessionTimeline = ({
  startDate,
  endDate,
}: {
  startDate?: Date
  endDate?: Date
}) => {
  const start = startDate?.getTime()
  const end = endDate?.getTime()

  if (start === undefined || end === undefined) {
    return true
  }

  if (Number.isNaN(start) || Number.isNaN(end)) {
    return true
  }

  return end - start >= MIN_TIMELINE_SPAN_MS
}

export const dateToValue = ({
  date,
  startDate,
  endDate,
}: {
  date: Date
  startDate: Date
  endDate: Date
}) => {
  if (endDate.getTime() === startDate.getTime()) {
    return 50
  }

  return (
    ((date.getTime() - startDate.getTime()) /
      (endDate.getTime() - startDate.getTime())) *
    100
  )
}

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
