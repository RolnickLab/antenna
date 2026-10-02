import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { TrackFrame } from './occurrence-details'

export interface ServerOccurrencePathFrame {
  detection_id: number
  bbox: number[] | null
  crop_url: string | null
  capture: {
    id: number
    timestamp: string | null
    width: number | null
    height: number | null
  }
}

/**
 * One frame of an occurrence's path. The capture's dimensions travel with the box
 * because the box is measured in that capture's pixel space, which need not match
 * the capture being drawn on.
 */
export interface PathFrame {
  bbox: number[]
  captureHeight: number | null
  captureId: string
  captureWidth: number | null
  /** The detection's crop, absent until one has been generated. */
  cropUrl?: string
  detectionId: string
  timestamp: Date | null
}

export const convertPathFrame = (
  frame: ServerOccurrencePathFrame
): PathFrame => ({
  bbox: frame.bbox ?? [],
  captureHeight: frame.capture.height,
  captureId: `${frame.capture.id}`,
  captureWidth: frame.capture.width,
  cropUrl: frame.crop_url ?? undefined,
  detectionId: `${frame.detection_id}`,
  timestamp: frame.capture.timestamp ? new Date(frame.capture.timestamp) : null,
})

/** A path as the track navigation reads it: newest first, undated frames at the epoch. */
export const getTrackFrames = (path: PathFrame[]): TrackFrame[] =>
  path
    .map((frame) => {
      const timestamp = frame.timestamp ?? new Date(0)

      return {
        bbox: frame.bbox,
        captureHeight: frame.captureHeight ?? undefined,
        captureId: frame.captureId,
        captureWidth: frame.captureWidth ?? undefined,
        cropUrl: frame.cropUrl,
        id: frame.detectionId,
        timestamp,
        timeLabel: getFormatedTimeString({
          date: timestamp,
          options: { second: true },
        }),
      }
    })
    .sort((f1, f2) => f2.timestamp.getTime() - f1.timestamp.getTime())
