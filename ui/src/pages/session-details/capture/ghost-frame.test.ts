import { PathFrame } from 'data-services/models/occurrence-path'
import { getGhostFrame } from './ghost-frame'

const frame = (overrides: Partial<PathFrame> = {}): PathFrame => ({
  bbox: [10, 10, 40, 40],
  captureHeight: 200,
  captureId: 'c1',
  captureWidth: 300,
  cropUrl: 'https://example.test/crop.jpg',
  detectionId: 'd1',
  timestamp: new Date(2026, 8, 1, 22, 46, 32),
  ...overrides,
})

describe('getGhostFrame', () => {
  it('withholds the crop until crops are asked for', () => {
    expect(getGhostFrame(frame(), false).cropUrl).toBeUndefined()
    expect(getGhostFrame(frame(), true).cropUrl).toBe(
      'https://example.test/crop.jpg'
    )
  })

  it('has no crop to offer for a frame whose crop has not been generated', () => {
    expect(
      getGhostFrame(frame({ cropUrl: undefined }), true).cropUrl
    ).toBeUndefined()
  })

  it('names the frame by its time, down to the second that separates captures', () => {
    expect(getGhostFrame(frame(), false).label).toContain('46:32')
  })

  it('stays labelled when the frame has no timestamp', () => {
    const label = getGhostFrame(frame({ timestamp: null }), false).label

    expect(label).not.toBe('')
    expect(label).not.toContain('undefined')
  })
})
