import { TimelineTick } from 'data-services/models/timeline-tick'
import { buildOccurrenceTimeline } from './occurrence-timeline'

const at = (minute: number, second = 0) =>
  new Date(2026, 8, 1, 22, minute, second)

// One-minute ticks from 22:00, the resolution the session timeline uses by default.
const buildTimeline = (capturesPerMinute: number[]) =>
  capturesPerMinute.map(
    (captures, minute) =>
      new TimelineTick({
        start: at(minute).toISOString(),
        end: at(minute + 1).toISOString(),
        first_capture: captures ? { id: minute } : null,
        top_capture: null,
        captures_count: captures,
        detections_count: 0,
        detections_avg: 0,
      })
  )

// A capture half-way through the tick for its minute.
const frame = (minute: number) => ({
  captureId: `c${minute}`,
  timestamp: at(minute, 30),
})

// A capture every other minute from 22:00 to 22:10.
const TIMELINE = buildTimeline([1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1])

describe('buildOccurrenceTimeline', () => {
  test('a lone frame is a dot on its capture spike, with no bar', () => {
    const { bars, dots } = buildOccurrenceTimeline([frame(4)], TIMELINE)

    expect(dots).toEqual([
      { captureId: 'c4', date: at(4), timestamp: at(4, 30) },
    ])
    expect(bars).toEqual([])
  })

  test('frames in consecutive captures share one bar across empty ticks', () => {
    const { bars, dots } = buildOccurrenceTimeline(
      [frame(2), frame(4), frame(6)],
      TIMELINE
    )

    expect(dots.map((dot) => dot.captureId)).toEqual(['c2', 'c4', 'c6'])
    expect(bars).toEqual([{ start: at(2), end: at(6) }])
  })

  test('a capture outside the occurrence splits its frames into two runs', () => {
    const { bars } = buildOccurrenceTimeline(
      [frame(0), frame(2), frame(6), frame(8)],
      TIMELINE
    )

    expect(bars).toEqual([
      { start: at(0), end: at(2) },
      { start: at(6), end: at(8) },
    ])
  })

  test('frames outside the timeline are left off', () => {
    const { bars, dots } = buildOccurrenceTimeline(
      [
        { captureId: 'before', timestamp: new Date(2026, 8, 1, 21, 50) },
        frame(0),
        frame(2),
        { captureId: 'after', timestamp: at(30) },
        { captureId: 'undated', timestamp: null },
      ],
      TIMELINE
    )

    expect(dots.map((dot) => dot.captureId)).toEqual(['c0', 'c2'])
    expect(bars).toEqual([{ start: at(0), end: at(2) }])
  })
})
