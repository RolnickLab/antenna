import { TimelineTick } from 'data-services/models/timeline-tick'
import {
  getCaptureIndex,
  getKeyStep,
  getNavigableCaptures,
  getStepTarget,
} from './timeline-navigation'

const at = (minute: number, second = 0) =>
  new Date(2026, 8, 1, 22, minute, second)

const tick = (minute: number, captureId?: string) =>
  ({
    startDate: at(minute),
    endDate: at(minute + 1),
    representativeCaptureId: captureId,
  } as TimelineTick)

// A capture every other minute, with an empty minute in between.
const TIMELINE = [tick(0, 'c0'), tick(1), tick(2, 'c2'), tick(3, 'c3')]
const CAPTURES = getNavigableCaptures(TIMELINE)

describe('getNavigableCaptures', () => {
  test('a tick holding no capture is not a stop', () => {
    expect(CAPTURES.map((capture) => capture.captureId)).toEqual([
      'c0',
      'c2',
      'c3',
    ])
  })
})

describe('getCaptureIndex', () => {
  test('a capture just past a stop keeps that position', () => {
    expect(
      getCaptureIndex({
        captureId: 'c2-10',
        captures: CAPTURES,
        date: at(2, 10),
      })
    ).toBe(1)
  })

  // Taking the stop it is nearest, rather than the one it follows, keeps a step back
  // on the stop it just passed instead of skipping over it.
  test('a capture nearer the next stop takes that position', () => {
    expect(
      getCaptureIndex({
        captureId: 'c2-40',
        captures: CAPTURES,
        date: at(2, 40),
      })
    ).toBe(2)
  })

  test('an unknown capture with no date has no position', () => {
    expect(getCaptureIndex({ captureId: 'gone', captures: CAPTURES })).toBe(-1)
  })
})

describe('getStepTarget', () => {
  test('stepping stops at the ends rather than running off them', () => {
    expect(
      getStepTarget({ captures: CAPTURES, index: 0, step: -1 })?.captureId
    ).toBe('c0')
    expect(
      getStepTarget({ captures: CAPTURES, index: 2, step: 1 })?.captureId
    ).toBe('c3')
  })

  test('home and end reach the first and last capture in one press', () => {
    expect(
      getStepTarget({
        captures: CAPTURES,
        index: 2,
        step: getKeyStep('Home') as number,
      })?.captureId
    ).toBe('c0')
    expect(
      getStepTarget({
        captures: CAPTURES,
        index: 0,
        step: getKeyStep('End') as number,
      })?.captureId
    ).toBe('c3')
  })

  test('an unknown position leaves the capture alone', () => {
    expect(
      getStepTarget({ captures: CAPTURES, index: -1, step: 1 })
    ).toBeUndefined()
  })
})

describe('getKeyStep', () => {
  test('a key the timeline does not claim is left to the browser', () => {
    expect(getKeyStep('Enter')).toBeUndefined()
    expect(getKeyStep('Tab')).toBeUndefined()
  })
})
