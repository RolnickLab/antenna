import { PathFrame } from 'data-services/models/occurrence-path'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'

/** What a box drawn from a neighbouring frame offers: the crop to fill it and the frame it steps to. */
export interface GhostFrame {
  captureId: string
  /** Absent unless crops were asked for and this frame has one. */
  cropUrl?: string
  label: string
  /** When the frame was captured, to the second that separates two captures. */
  time: string
}

export const getGhostFrame = (
  frame: PathFrame,
  showCrops: boolean
): GhostFrame => {
  const time = frame.timestamp
    ? getFormatedTimeString({
        date: frame.timestamp,
        options: { second: true },
      })
    : translate(STRING.VALUE_NOT_AVAILABLE)

  return {
    captureId: frame.captureId,
    cropUrl: showCrops ? frame.cropUrl : undefined,
    label: translate(STRING.TRACK_PATH_GO_TO_FRAME, { time }),
    time,
  }
}
