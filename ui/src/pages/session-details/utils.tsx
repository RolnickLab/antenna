import { TimelineTick } from 'data-services/models/timeline-tick'

export const findClosestCaptureId = ({
  maxDate,
  minDate,
  snapToDetections,
  snapToTaxon,
  targetDate,
  timeline,
}: {
  maxDate?: Date
  minDate?: Date
  snapToDetections?: boolean
  // Only ticks with detections of the timeline's taxon filter, landing on the
  // capture that has the most of them.
  snapToTaxon?: boolean
  targetDate: Date
  timeline: TimelineTick[]
}) => {
  let closestCaptureId: string | undefined
  let smallestDifference = Infinity

  timeline.forEach((timelineTick) => {
    const captureId = snapToTaxon
      ? timelineTick.taxonTopCaptureId ?? timelineTick.representativeCaptureId
      : timelineTick.representativeCaptureId

    if (!captureId) {
      return
    }

    if (snapToDetections && !timelineTick.numDetections) {
      return
    }

    if (snapToTaxon && !timelineTick.numTaxonDetections) {
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
      closestCaptureId = captureId
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
