import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'

export type ServerCapture = any // TODO: Update this type

export type CaptureDetection = {
  bbox: number[]
  id: string
  label: string
  occurrenceId: string
}

export class Capture {
  protected readonly _capture: ServerCapture
  private readonly _detections: CaptureDetection[] = []

  public constructor(capture: ServerCapture) {
    this._capture = capture

    if (capture.detections?.length) {
      this._detections = capture.detections.map((detection: any) => ({
        bbox: detection.bbox,
        id: `${detection.id}`,
        label: detection.occurrence.determination.name,
        occurrenceId: `${detection.occurrence.id}`,
      }))
    }
  }

  get detections(): CaptureDetection[] {
    return this._detections
  }

  get height(): number {
    return this._capture.height
  }

  get id(): string {
    return `${this._capture.id}`
  }

  get numDetections(): number {
    return this._capture.detections_count
  }

  get src(): string {
    return `${this._capture.url}`
  }

  get timeLabel(): string {
    return getFormatedTimeString({ date: new Date(this._capture.timestamp) })
  }

  get width(): number {
    return this._capture.width
  }
}
