import { CaptureDetails } from 'data-services/models/capture-details'
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

const findNextCaptureWithDetections = ({
  date,
  timeline,
}: {
  date: Date
  timeline: TimelineTick[]
}) =>
  findClosestCaptureId({
    minDate: date,
    snapToDetections: true,
    targetDate: date,
    timeline,
  })

const findPrevCaptureWithDetections = ({
  date,
  timeline,
}: {
  date: Date
  timeline: TimelineTick[]
}) =>
  findClosestCaptureId({
    maxDate: date,
    snapToDetections: true,
    targetDate: date,
    timeline,
  })

type CaptureNeighbours = Pick<
  CaptureDetails,
  'date' | 'nextCaptureWithDetectionsId' | 'prevCaptureWithDetectionsId'
>

// The server sees every capture; the timeline keeps one per minute, so it only
// stands in when the capture was fetched without the server's answer.
export const getNextCaptureWithDetectionsId = ({
  capture,
  timeline,
}: {
  capture: CaptureNeighbours
  timeline: TimelineTick[]
}) =>
  capture.nextCaptureWithDetectionsId === undefined
    ? findNextCaptureWithDetections({ date: capture.date, timeline })
    : capture.nextCaptureWithDetectionsId ?? undefined

export const getPrevCaptureWithDetectionsId = ({
  capture,
  timeline,
}: {
  capture: CaptureNeighbours
  timeline: TimelineTick[]
}) =>
  capture.prevCaptureWithDetectionsId === undefined
    ? findPrevCaptureWithDetections({ date: capture.date, timeline })
    : capture.prevCaptureWithDetectionsId ?? undefined

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
