import { TrackFrame } from 'data-services/models/occurrence-details'
import { getTrackNavigation } from './track-navigation'

const at = (minute: number) => new Date(2026, 8, 1, 22, minute)

const frame = (minute: number): TrackFrame => ({
  bbox: [],
  captureId: `c${minute}`,
  id: `d${minute}`,
  timestamp: at(minute),
  timeLabel: '',
})

// Newest first, the order OccurrenceDetails.frames holds them in.
const FRAMES = [frame(30), frame(20), frame(10)]

describe('getTrackNavigation', () => {
  test('a capture holding a frame steps to its neighbours in the track', () => {
    const navigation = getTrackNavigation({
      captureDate: at(20),
      captureId: 'c20',
      frames: FRAMES,
    })

    expect(navigation.position).toEqual({ kind: 'frame', index: 2 })
    expect(navigation.previous?.id).toBe('d10')
    expect(navigation.next?.id).toBe('d30')
    expect(navigation.first?.id).toBe('d10')
    expect(navigation.last?.id).toBe('d30')
  })

  test('a capture the track skips steps to the nearest frame on either side', () => {
    const navigation = getTrackNavigation({
      captureDate: at(25),
      captureId: 'c25',
      frames: FRAMES,
    })

    expect(navigation.position).toEqual({ kind: 'between', before: 2 })
    expect(navigation.previous?.id).toBe('d20')
    expect(navigation.next?.id).toBe('d30')
  })

  test('a capture before the first frame has no earlier frame to step to', () => {
    const navigation = getTrackNavigation({
      captureDate: at(5),
      captureId: 'c5',
      frames: FRAMES,
    })

    expect(navigation.position).toEqual({ kind: 'before-first' })
    expect(navigation.previous).toBeUndefined()
    expect(navigation.next?.id).toBe('d10')
  })

  test('a capture after the last frame has no later frame to step to', () => {
    const navigation = getTrackNavigation({
      captureDate: at(40),
      captureId: 'c40',
      frames: FRAMES,
    })

    expect(navigation.position).toEqual({ kind: 'after-last' })
    expect(navigation.previous?.id).toBe('d30')
    expect(navigation.next).toBeUndefined()
  })
})
