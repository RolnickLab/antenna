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
