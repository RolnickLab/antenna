import { TimelineTick } from 'data-services/models/timeline-tick'
import {
  buildOccurrenceTimeline,
  TimelineSpan,
  getDurationLabel,
} from './occurrence-timeline'

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

const bounds = (spans: TimelineSpan[]) =>
  spans.map(({ start, end }) => ({ start, end }))

describe('buildOccurrenceTimeline', () => {
  test('a lone frame is a span on its own capture spike', () => {
    expect(buildOccurrenceTimeline([frame(4)], TIMELINE)).toEqual([
      {
        start: at(4),
        end: at(4),
        frames: [{ captureId: 'c4', date: at(4), timestamp: at(4, 30) }],
      },
    ])
  })

  test('frames in consecutive captures share one span across empty ticks', () => {
    const spans = buildOccurrenceTimeline(
      [frame(2), frame(4), frame(6)],
      TIMELINE
    )

    expect(bounds(spans)).toEqual([{ start: at(2), end: at(6) }])
    expect(spans[0].frames.map((f) => f.captureId)).toEqual(['c2', 'c4', 'c6'])
  })

  test('a capture outside the occurrence splits its frames into two spans', () => {
    const spans = buildOccurrenceTimeline(
      [frame(0), frame(2), frame(6), frame(8)],
      TIMELINE
    )

    expect(bounds(spans)).toEqual([
      { start: at(0), end: at(2) },
      { start: at(6), end: at(8) },
    ])
  })

  test('another capture in a tick that holds a frame does not split the span', () => {
    const spans = buildOccurrenceTimeline(
      [frame(0), frame(1)],
      buildTimeline([2, 2])
    )

    expect(bounds(spans)).toEqual([{ start: at(0), end: at(1) }])
  })

  test('frames outside the timeline are left off', () => {
    const spans = buildOccurrenceTimeline(
      [
        { captureId: 'before', timestamp: new Date(2026, 8, 1, 21, 50) },
        frame(0),
        frame(2),
        { captureId: 'after', timestamp: at(30) },
        { captureId: 'undated', timestamp: null },
      ],
      TIMELINE
    )

    expect(bounds(spans)).toEqual([{ start: at(0), end: at(2) }])
    expect(spans[0].frames.map((f) => f.captureId)).toEqual(['c0', 'c2'])
  })
})

describe('getDurationLabel', () => {
  test('rounds to seconds, minutes, or hours and minutes', () => {
    expect(getDurationLabel(2_000)).toBe('2 s')
    expect(getDurationLabel((8 * 60 + 22) * 1000)).toBe('8 min')
    expect(getDurationLabel(72 * 60 * 1000)).toBe('1 h 12 min')
  })
})
