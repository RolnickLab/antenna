import { PathFrame } from 'data-services/models/occurrence-path'
import { TimelineTick } from 'data-services/models/timeline-tick'
import { STRING, translate } from 'utils/language'

export interface TimelineFrame {
  captureId: string
  /** Start of the tick holding the capture, which is where the plot draws its spike. */
  date: Date
  timestamp: Date
}

/** A run of frames drawn as one block, from the first frame's spike to the last one's. */
export interface TimelineSpan {
  end: Date
  frames: TimelineFrame[]
  start: Date
}

// A tick holds the captures after its start up to and including its end; the first
// tick also holds its start.
const findTickIndex = (timeline: TimelineTick[], date: Date) => {
  const time = date.getTime()
  const last = timeline[timeline.length - 1]

  if (
    !last ||
    time < timeline[0].startDate.getTime() ||
    time > last.endDate.getTime()
  ) {
    return -1
  }

  let low = 0
  let high = timeline.length - 1

  while (low < high) {
    const middle = Math.floor((low + high) / 2)

    if (timeline[middle].endDate.getTime() < time) {
      low = middle + 1
    } else {
      high = middle
    }
  }

  return low
}

/**
 * Where an occurrence's frames fall on the session timeline, grouped into runs. A run
 * continues across ticks with no captures and breaks at a tick that holds captures but
 * none of the occurrence's frames.
 */
export const buildOccurrenceTimeline = (
  frames: Pick<PathFrame, 'captureId' | 'timestamp'>[],
  timeline: TimelineTick[]
): TimelineSpan[] => {
  const byCapture = new Map<string, { frame: TimelineFrame; tick: number }>()

  frames.forEach(({ captureId, timestamp }) => {
    const tick = timestamp ? findTickIndex(timeline, timestamp) : -1

    if (timestamp && tick !== -1 && !byCapture.has(captureId)) {
      byCapture.set(captureId, {
        frame: { captureId, date: timeline[tick].startDate, timestamp },
        tick,
      })
    }
  })

  const placed = [...byCapture.values()].sort(
    (a, b) => a.frame.timestamp.getTime() - b.frame.timestamp.getTime()
  )

  // Ticks only count their captures, so a tick that also holds a frame never breaks a run.
  const hasCaptureBetween = (fromTick: number, toTick: number) =>
    timeline.slice(fromTick + 1, toTick).some((tick) => tick.numCaptures > 0)

  const spans: TimelineSpan[] = []
  let previousTick = -1

  placed.forEach(({ frame, tick }) => {
    const current = spans[spans.length - 1]

    if (current && !hasCaptureBetween(previousTick, tick)) {
      current.frames.push(frame)
      current.end = frame.date
    } else {
      spans.push({ end: frame.date, frames: [frame], start: frame.date })
    }

    previousTick = tick
  })

  return spans
}

/** A short, rounded length of time, such as "42 s", "8 min" or "1 h 12 min". */
export const getDurationLabel = (milliseconds: number) => {
  const seconds = Math.round(milliseconds / 1000)

  if (seconds < 60) {
    return translate(STRING.TIMELINE_DURATION_SECONDS, {
      seconds: String(seconds),
    })
  }

  const minutes = Math.round(seconds / 60)

  if (minutes < 60) {
    return translate(STRING.TIMELINE_DURATION_MINUTES, {
      minutes: String(minutes),
    })
  }

  return translate(STRING.TIMELINE_DURATION_HOURS, {
    hours: String(Math.floor(minutes / 60)),
    minutes: String(minutes % 60),
  })
}
