import { PathFrame } from 'data-services/models/occurrence-path'
import { TimelineTick } from 'data-services/models/timeline-tick'

export interface TimelineDot {
  captureId: string
  /** Start of the tick holding the capture, which is where the plot draws its spike. */
  date: Date
  timestamp: Date
}

export interface TimelineBar {
  end: Date
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
 * Where an occurrence's frames fall on the session timeline: a dot per capture, and a
 * bar over each run of frames with no other capture of the session between them.
 */
export const buildOccurrenceTimeline = (
  frames: Pick<PathFrame, 'captureId' | 'timestamp'>[],
  timeline: TimelineTick[]
): { bars: TimelineBar[]; dots: TimelineDot[] } => {
  const byCapture = new Map<
    string,
    { captureId: string; tick: number; timestamp: Date }
  >()

  frames.forEach(({ captureId, timestamp }) => {
    const tick = timestamp ? findTickIndex(timeline, timestamp) : -1

    if (timestamp && tick !== -1 && !byCapture.has(captureId)) {
      byCapture.set(captureId, { captureId, tick, timestamp })
    }
  })

  const placed = [...byCapture.values()].sort(
    (a, b) => a.timestamp.getTime() - b.timestamp.getTime()
  )
  const framesPerTick = new Map<number, number>()
  placed.forEach(({ tick }) =>
    framesPerTick.set(tick, (framesPerTick.get(tick) ?? 0) + 1)
  )

  // A tick can hold several captures without saying in what order, so any capture
  // outside the occurrence in the ticks spanned breaks the run.
  const isJoined = (fromTick: number, toTick: number) => {
    for (let index = fromTick; index <= toTick; index++) {
      if (timeline[index].numCaptures > (framesPerTick.get(index) ?? 0)) {
        return false
      }
    }

    return true
  }

  const bars: TimelineBar[] = []
  let runStart = placed[0]

  placed.forEach((frame, index) => {
    const next = placed[index + 1]

    if (next && isJoined(frame.tick, next.tick)) {
      return
    }

    if (runStart && runStart !== frame) {
      bars.push({
        start: timeline[runStart.tick].startDate,
        end: timeline[frame.tick].startDate,
      })
    }

    runStart = next
  })

  return {
    bars,
    dots: placed.map(({ captureId, tick, timestamp }) => ({
      captureId,
      date: timeline[tick].startDate,
      timestamp,
    })),
  }
}
