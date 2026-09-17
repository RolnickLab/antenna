import { TimelineTick } from 'data-services/models/timeline-tick'
import {
  getNextCaptureWithDetectionsId,
  getPrevCaptureWithDetectionsId,
  showSessionTimeline,
} from './utils'

const at = (minute: number, second = 0) =>
  new Date(2026, 8, 1, 0, minute, second)

const tick = (minute: number, captureId: string, numDetections = 1) =>
  ({
    startDate: at(minute),
    endDate: at(minute + 1),
    numDetections,
    representativeCaptureId: captureId,
  } as TimelineTick)

// One tick per minute: the 12:03 tick stands for a burst of captures seconds apart.
const TIMELINE = [tick(2, 'c2'), tick(3, 'c3'), tick(9, 'c9')]

describe('capture with detections on either side', () => {
  test('the server answer wins, so a burst inside one minute is not skipped', () => {
    const capture = {
      date: at(3, 31),
      nextCaptureWithDetectionsId: 'c3-33',
      prevCaptureWithDetectionsId: 'c3-29',
    }

    expect(
      getNextCaptureWithDetectionsId({ capture, timeline: TIMELINE })
    ).toBe('c3-33')
    expect(
      getPrevCaptureWithDetectionsId({ capture, timeline: TIMELINE })
    ).toBe('c3-29')
  })

  test('null from the server means there is none, without asking the timeline', () => {
    const capture = {
      date: at(3, 31),
      nextCaptureWithDetectionsId: null,
      prevCaptureWithDetectionsId: null,
    }

    expect(
      getNextCaptureWithDetectionsId({ capture, timeline: TIMELINE })
    ).toBeUndefined()
    expect(
      getPrevCaptureWithDetectionsId({ capture, timeline: TIMELINE })
    ).toBeUndefined()
  })

  test('without the server answer the timeline stands in', () => {
    const capture = {
      date: at(3, 31),
      nextCaptureWithDetectionsId: undefined,
      prevCaptureWithDetectionsId: undefined,
    }

    expect(
      getNextCaptureWithDetectionsId({ capture, timeline: TIMELINE })
    ).toBe('c9')
    expect(
      getPrevCaptureWithDetectionsId({ capture, timeline: TIMELINE })
    ).toBe('c2')
  })
})

describe('session timeline visibility', () => {
  const startDate = at(0)

  test('a session spanning less than a minute has no timeline', () => {
    expect(showSessionTimeline({ startDate, endDate: at(0, 59) })).toBe(false)
  })

  test('a session spanning a full minute keeps its timeline', () => {
    expect(showSessionTimeline({ startDate, endDate: at(1) })).toBe(true)
  })

  test('an unknown span keeps the timeline rather than hiding it', () => {
    expect(showSessionTimeline({ startDate, endDate: undefined })).toBe(true)
    expect(showSessionTimeline({ startDate, endDate: new Date(NaN) })).toBe(
      true
    )
  })
})
