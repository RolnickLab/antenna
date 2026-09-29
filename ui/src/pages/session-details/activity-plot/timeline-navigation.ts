import { TimelineTick } from 'data-services/models/timeline-tick'

/** A capture a keyboard user can step to, in session order. */
export interface NavigableCapture {
  captureId: string
  date: Date
}

// Page keys cross a long night in a handful of presses.
const CAPTURES_PER_PAGE = 10

const STEP_BY_KEY: { [key: string]: number } = {
  ArrowDown: -1,
  ArrowLeft: -1,
  ArrowRight: 1,
  ArrowUp: 1,
  End: Infinity,
  Home: -Infinity,
  PageDown: -CAPTURES_PER_PAGE,
  PageUp: CAPTURES_PER_PAGE,
}

/** How many captures a key moves, or undefined for a key the timeline leaves alone. */
export const getKeyStep = (key: string): number | undefined => STEP_BY_KEY[key]

/** The timeline keeps one capture per tick, so those are the stops along the session. */
export const getNavigableCaptures = (
  timeline: TimelineTick[]
): NavigableCapture[] =>
  timeline.flatMap((tick) =>
    tick.representativeCaptureId
      ? [{ captureId: tick.representativeCaptureId, date: tick.startDate }]
      : []
  )

/**
 * Where the active capture sits among the stops. A capture reached with the previous
 * and next buttons is often not a stop itself, so it falls back to the nearest stop in
 * time and reports -1 only when there is nothing to match on.
 */
export const getCaptureIndex = ({
  captureId,
  captures,
  date,
}: {
  captureId?: string
  captures: NavigableCapture[]
  date?: Date
}) => {
  const exact = captures.findIndex((capture) => capture.captureId === captureId)

  if (exact !== -1 || !date) {
    return exact
  }

  let closest = -1
  let smallestDifference = Infinity

  captures.forEach((capture, index) => {
    const difference = Math.abs(capture.date.getTime() - date.getTime())

    if (difference < smallestDifference) {
      smallestDifference = difference
      closest = index
    }
  })

  return closest
}

/** The capture a step lands on, held inside the ends of the session. */
export const getStepTarget = ({
  captures,
  index,
  step,
}: {
  captures: NavigableCapture[]
  index: number
  step: number
}): NavigableCapture | undefined => {
  if (index === -1 || !captures.length) {
    return undefined
  }

  return captures[Math.min(Math.max(index + step, 0), captures.length - 1)]
}
