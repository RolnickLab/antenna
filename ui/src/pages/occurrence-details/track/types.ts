export type FrameAction = 'split' | 'remove' | 'move'

/**
 * A frame action described in full when it was asked for: the dialog outlives the
 * frame, since the edit moves that frame off this occurrence.
 */
export interface PendingFrameAction {
  action: FrameAction
  captureId?: string
  detectionId: string
  /** Frames a split would move: this frame and every later one. */
  movedBySplit: number
  timeLabel: string
  total: number
}
