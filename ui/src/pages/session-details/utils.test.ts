import {
  ServerTimelineTick,
  TimelineTick,
} from 'data-services/models/timeline-tick'
import { findClosestCaptureId } from './utils'

const tick = (
  minute: number,
  overrides: Partial<ServerTimelineTick> = {}
): TimelineTick =>
  new TimelineTick({
    start: `2026-01-01T22:${String(minute).padStart(2, '0')}:00`,
    end: `2026-01-01T22:${String(minute + 1).padStart(2, '0')}:00`,
    first_capture: { id: minute * 10 },
    top_capture: { id: minute * 10 + 1 },
    captures_count: 1,
    detections_count: 0,
    detections_avg: 0,
    taxon_detections_count: null,
    taxon_top_capture: null,
    ...overrides,
  })

// Minute 1 has detections but none of the taxon; minute 3 has the taxon.
const TIMELINE = [
  tick(0),
  tick(1, { detections_count: 4, taxon_detections_count: 0 }),
  tick(2),
  tick(3, {
    detections_count: 2,
    taxon_detections_count: 1,
    taxon_top_capture: { id: 99 },
  }),
]

const target = (minute: number) =>
  new Date(`2026-01-01T22:${String(minute).padStart(2, '0')}:00`)

describe('findClosestCaptureId', () => {
  test('snap to detections stops at the next capture with any detection', () => {
    expect(
      findClosestCaptureId({
        minDate: target(0),
        snapToDetections: true,
        targetDate: target(0),
        timeline: TIMELINE,
      })
    ).toBe('11')
  })

  test('snap to taxon skips captures without that taxon and lands on its top capture', () => {
    expect(
      findClosestCaptureId({
        minDate: target(0),
        snapToTaxon: true,
        targetDate: target(0),
        timeline: TIMELINE,
      })
    ).toBe('99')
  })

  test('snap to taxon finds nothing when the taxon never appears', () => {
    expect(
      findClosestCaptureId({
        snapToTaxon: true,
        targetDate: target(0),
        timeline: TIMELINE.slice(0, 3),
      })
    ).toBeUndefined()
  })
})
