import { CaptureNeighbourIds, demandBand, planPreload } from './capture-preload'

// A session of six captures where 1, 3 and 5 carry detections. Nothing is
// known about 6, standing in for a capture that has not been read yet.
const SESSION: { [id: string]: CaptureNeighbourIds } = {
  '1': { nextCaptureId: '2', nextCaptureWithDetectionsId: '3' },
  '2': { nextCaptureId: '3', prevCaptureId: '1' },
  '3': {
    nextCaptureId: '4',
    nextCaptureWithDetectionsId: '5',
    prevCaptureId: '2',
    prevCaptureWithDetectionsId: '1',
  },
  '4': { nextCaptureId: '5', prevCaptureId: '3' },
  '5': {
    nextCaptureId: '6',
    prevCaptureId: '4',
    prevCaptureWithDetectionsId: '3',
  },
}

const lookup = (id: string) => SESSION[id]

describe('planPreload', () => {
  test('plans both directions, detections neighbours first', () => {
    expect(planPreload({ startId: '3', lookup })).toEqual(['5', '1', '4', '2'])
  })

  test('plans a capture once, however many directions reach it', () => {
    // From 1 the detections chain reaches 3 then 5, and the plain chain reaches
    // 2 then 3 — a second claim on 3 adds nothing to fetch.
    expect(planPreload({ startId: '1', lookup })).toEqual(['3', '2', '5'])
  })

  test('stops every direction at the requested depth', () => {
    expect(planPreload({ startId: '1', depth: 1, lookup })).toEqual(['3', '2'])
  })

  test('stops a direction whose neighbour has not been read yet', () => {
    // 6 is planned, but the capture after it stays unknown until 6 is read.
    expect(planPreload({ startId: '5', lookup })).toEqual(['3', '6', '4', '1'])
  })
})

describe('demandBand', () => {
  test('reads the same until the demand crosses a thumbnail size', () => {
    // The medium thumbnail is 1024px wide and covers a 20% upscale.
    expect(demandBand(600)).toBe(demandBand(1228))
    expect(demandBand(1229)).not.toBe(demandBand(1228))
  })

  test('rises once per thumbnail size the demand outgrows', () => {
    expect([demandBand(600), demandBand(2000), demandBand(4000)]).toEqual([
      0, 1, 2,
    ])
  })
})
