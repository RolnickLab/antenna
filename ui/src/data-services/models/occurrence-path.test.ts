import { getTrackFrames, PathFrame } from './occurrence-path'

const pathFrame = (id: string, timestamp: string | null): PathFrame => ({
  bbox: [0, 0, 10, 10],
  captureHeight: 100,
  captureId: `c${id}`,
  captureWidth: null,
  cropUrl: `https://example.com/${id}.jpg`,
  detectionId: id,
  timestamp: timestamp ? new Date(timestamp) : null,
})

describe('track frames from a path', () => {
  test('run newest first and keep the crop and capture of each frame', () => {
    const frames = getTrackFrames([
      pathFrame('1', '2026-09-09T02:01:00'),
      pathFrame('2', '2026-09-09T02:03:00'),
      pathFrame('3', '2026-09-09T02:02:00'),
    ])

    expect(frames.map((frame) => frame.id)).toEqual(['2', '3', '1'])
    expect(frames[0]).toMatchObject({
      captureId: 'c2',
      captureWidth: undefined,
      cropUrl: 'https://example.com/2.jpg',
    })
  })

  test('an undated frame sorts as the oldest', () => {
    const frames = getTrackFrames([
      pathFrame('1', null),
      pathFrame('2', '2026-09-09T02:01:00'),
    ])

    expect(frames.map((frame) => frame.id)).toEqual(['2', '1'])
  })
})
