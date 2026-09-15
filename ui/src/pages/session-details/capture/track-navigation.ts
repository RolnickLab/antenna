import { TrackFrame } from 'data-services/models/occurrence-details'
import { PathFrame } from 'data-services/models/occurrence-path'

export type TrackPosition =
  | { kind: 'frame'; index: number }
  | { kind: 'between'; before: number }
  | { kind: 'before-first' }
  | { kind: 'after-last' }

export interface TrackNavigation {
  first?: TrackFrame
  last?: TrackFrame
  next?: TrackFrame
  position?: TrackPosition
  previous?: TrackFrame
  total: number
}

/**
 * Where a capture sits in a track, and the frames the track buttons step to from it.
 * Previous and next go by time, so they also work from a capture the track skips.
 */
export const getTrackNavigation = ({
  captureDate,
  captureId,
  frames,
}: {
  captureDate?: Date
  captureId?: string
  frames: TrackFrame[]
}): TrackNavigation => {
  const ordered = [...frames].sort(
    (f1, f2) => f1.timestamp.getTime() - f2.timestamp.getTime()
  )
  const total = ordered.length
  const first = ordered[0]
  const last = ordered[total - 1]
  const index = captureId
    ? ordered.findIndex((frame) => frame.captureId === captureId)
    : -1

  if (index >= 0) {
    return {
      first,
      last,
      next: ordered[index + 1],
      position: { kind: 'frame', index: index + 1 },
      previous: ordered[index - 1],
      total,
    }
  }

  if (!captureDate || !total) {
    return { first, last, total }
  }

  const time = captureDate.getTime()
  const before = ordered.filter(
    (frame) => frame.timestamp.getTime() < time
  ).length
  let position: TrackPosition = { kind: 'between', before }

  if (before === 0) {
    position = { kind: 'before-first' }
  } else if (before === total) {
    position = { kind: 'after-last' }
  }

  return {
    first,
    last,
    next: ordered.find((frame) => frame.timestamp.getTime() > time),
    position,
    previous: before > 0 ? ordered[before - 1] : undefined,
    total,
  }
}

/** The path frame closest in time to a capture, so the operator can jump back onto the track. */
export const getNearestPathFrame = (frames: PathFrame[], date?: Date) => {
  const dated = frames.filter(
    (frame): frame is PathFrame & { timestamp: Date } => !!frame.timestamp
  )

  if (!date || !dated.length) {
    return frames[0]
  }

  const distance = (frame: { timestamp: Date }) =>
    Math.abs(frame.timestamp.getTime() - date.getTime())

  return dated.reduce((nearest, frame) =>
    distance(frame) < distance(nearest) ? frame : nearest
  )
}
