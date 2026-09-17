import { STRING } from 'utils/language'
import { getExtendClick, getExtendClickHint } from './extend-click'

const TRACK_ID = 't1'

// The track holds d1 on capture c1 and d2 on capture c2.
const FRAMES = [
  { captureId: 'c1', id: 'd1' },
  { captureId: 'c2', id: 'd2' },
]

const box = (
  id: string,
  occurrenceId?: string,
  frameCount = occurrenceId ? 1 : 0
) => ({ frameCount, id, label: 'Moth', occurrenceId })

describe('getExtendClick', () => {
  test('a box on a capture the track skips is added to the track', () => {
    expect(
      getExtendClick({
        captureId: 'c3',
        detection: box('d3', 'o3'),
        frames: FRAMES,
        occurrenceId: TRACK_ID,
      })
    ).toEqual({ kind: 'add', detectionId: 'd3' })
  })

  test('a box of a multi-frame occurrence asks whether to merge or move', () => {
    expect(
      getExtendClick({
        captureId: 'c3',
        detection: box('d3', 'o3', 4),
        frames: FRAMES,
        occurrenceId: TRACK_ID,
      })
    ).toEqual({
      kind: 'choose',
      choice: {
        detectionId: 'd3',
        frameCount: 4,
        label: 'Moth #o3',
        occurrenceId: 'o3',
      },
    })
  })

  test('a box already in the track asks to remove it', () => {
    expect(
      getExtendClick({
        captureId: 'c2',
        detection: box('d2', TRACK_ID, 2),
        frames: FRAMES,
        occurrenceId: TRACK_ID,
      })
    ).toEqual({ kind: 'remove', detectionId: 'd2' })
  })

  test('another box on a covered capture asks to replace the frame, even from a longer track', () => {
    expect(
      getExtendClick({
        captureId: 'c2',
        detection: box('d9', 'o9', 5),
        frames: FRAMES,
        occurrenceId: TRACK_ID,
      })
    ).toEqual({
      kind: 'replace',
      addDetectionId: 'd9',
      removeDetectionId: 'd2',
    })
  })

  test("the track's only frame is neither removed nor replaced", () => {
    const frames = [FRAMES[0]]

    expect(
      getExtendClick({
        captureId: 'c1',
        detection: box('d1', TRACK_ID),
        frames,
        occurrenceId: TRACK_ID,
      })
    ).toEqual({ kind: 'only-frame' })
    expect(
      getExtendClick({
        captureId: 'c1',
        detection: box('d9'),
        frames,
        occurrenceId: TRACK_ID,
      })
    ).toEqual({ kind: 'only-frame' })
  })
})

describe('getExtendClickHint', () => {
  const hintFor = (
    captureId: string,
    detection: ReturnType<typeof box>,
    frames = FRAMES
  ) =>
    getExtendClickHint(
      getExtendClick({ captureId, detection, frames, occurrenceId: TRACK_ID })
    )

  test('a box that would join the track is marked with a plus', () => {
    expect(hintFor('c3', box('d3', 'o3'))).toEqual({
      indicator: 'add',
      string: STRING.TRACK_MATCH_CLICK_ADD,
    })
    expect(hintFor('c3', box('d3', 'o3', 4))).toEqual({
      indicator: 'add',
      string: STRING.TRACK_MATCH_CLICK_CHOOSE,
    })
  })

  test("the track's own box is marked with a minus", () => {
    expect(hintFor('c2', box('d2', TRACK_ID, 2))).toEqual({
      indicator: 'remove',
      string: STRING.TRACK_MATCH_CLICK_REMOVE,
    })
  })

  test('another box on a covered capture offers to replace the frame', () => {
    expect(hintFor('c2', box('d9', 'o9'))).toEqual({
      indicator: 'replace',
      string: STRING.TRACK_MATCH_CLICK_REPLACE,
    })
  })

  test("the track's only frame is marked as blocked", () => {
    expect(hintFor('c1', box('d1', TRACK_ID), [FRAMES[0]])).toEqual({
      indicator: 'blocked',
      string: STRING.TRACK_EXTEND_ONLY_FRAME,
    })
  })
})
