import { PathFrame } from 'data-services/models/occurrence-path'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'

/** What a box drawn from a neighbouring frame offers: the crop to fill it and the frame it steps to. */
export interface GhostFrame {
  captureId: string
  /** Absent unless crops were asked for and this frame has one. */
  cropUrl?: string
  label: string
}

export const getGhostFrame = (
  frame: PathFrame,
  showCrops: boolean
): GhostFrame => ({
  captureId: frame.captureId,
  cropUrl: showCrops ? frame.cropUrl : undefined,
  label: translate(STRING.TRACK_PATH_GO_TO_FRAME, {
    time: frame.timestamp
      ? getFormatedTimeString({
          date: frame.timestamp,
          options: { second: true },
        })
      : translate(STRING.VALUE_NOT_AVAILABLE),
  }),
})
