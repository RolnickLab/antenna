import { CaptureDetection } from 'data-services/models/capture'
import { TrackFrame } from 'data-services/models/occurrence-details'
import { STRING } from 'utils/language'

/** A clicked frame whose own occurrence spans several frames, so the reviewer picks what to move. */
export interface ExtendChoice {
  detectionId: string
  frameCount: number
  /** How the clicked occurrence is named in the dialog: its determination and its id. */
  label: string
  occurrenceId: string
}

export type ExtendClick =
  | { kind: 'add'; detectionId: string }
  | { kind: 'choose'; choice: ExtendChoice }
  | { kind: 'only-frame' }
  | { kind: 'remove'; detectionId: string }
  | { kind: 'replace'; addDetectionId: string; removeDetectionId: string }

/** A correction that waits for the reviewer to confirm it in the bar. */
export type ExtendPending = Extract<ExtendClick, { kind: 'remove' | 'replace' }>

/**
 * What a box click in extend mode asks for. One animal cannot appear twice in a
 * capture, so a click on a capture the track covers swaps its frame rather than adding.
 */
export const getExtendClick = ({
  captureId,
  detection,
  frames,
  occurrenceId,
}: {
  captureId?: string
  detection: Pick<
    CaptureDetection,
    'frameCount' | 'id' | 'label' | 'occurrenceId'
  >
  /** The frames of the track being extended. */
  frames: Pick<TrackFrame, 'captureId' | 'id'>[]
  occurrenceId: string
}): ExtendClick => {
  const inTrack =
    detection.occurrenceId === occurrenceId ||
    frames.some((frame) => frame.id === detection.id)
  const frameOnCapture = captureId
    ? frames.find((frame) => frame.captureId === captureId)
    : undefined

  // The server refuses to empty an occurrence, and a swap removes before it adds.
  if ((inTrack || frameOnCapture) && frames.length <= 1) {
    return { kind: 'only-frame' }
  }

  if (inTrack) {
    return { kind: 'remove', detectionId: detection.id }
  }

  if (frameOnCapture) {
    return {
      kind: 'replace',
      addDetectionId: detection.id,
      removeDetectionId: frameOnCapture.id,
    }
  }

  if (detection.occurrenceId && detection.frameCount > 1) {
    return {
      kind: 'choose',
      choice: {
        detectionId: detection.id,
        frameCount: detection.frameCount,
        label: `${detection.label} #${detection.occurrenceId}`,
        occurrenceId: detection.occurrenceId,
      },
    }
  }

  return { kind: 'add', detectionId: detection.id }
}

export type ExtendClickIndicator = 'add' | 'blocked' | 'remove' | 'replace'

const CLICK_HINTS: Record<
  ExtendClick['kind'],
  { indicator: ExtendClickIndicator; string: STRING }
> = {
  add: { indicator: 'add', string: STRING.TRACK_MATCH_CLICK_ADD },
  choose: { indicator: 'add', string: STRING.TRACK_MATCH_CLICK_CHOOSE },
  'only-frame': {
    indicator: 'blocked',
    string: STRING.TRACK_EXTEND_ONLY_FRAME,
  },
  remove: { indicator: 'remove', string: STRING.TRACK_MATCH_CLICK_REMOVE },
  replace: { indicator: 'replace', string: STRING.TRACK_MATCH_CLICK_REPLACE },
}

/** What a box's tooltip says a click will do, read from the decision the click acts on. */
export const getExtendClickHint = (click: ExtendClick) =>
  CLICK_HINTS[click.kind]
