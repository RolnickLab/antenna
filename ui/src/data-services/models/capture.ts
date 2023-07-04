import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'

export type ServerCapture = any // TODO: Update this type

export class Capture {
  private readonly _capture: ServerCapture

  public constructor(capture: ServerCapture) {
    this._capture = capture
  }

  get numDetections(): number {
    return this._capture.detections_count
  }

  get height(): number {
    return this._capture.height
  }

  get id(): string {
    return `${this._capture.id}`
  }

  get src(): string {
    return `${this._capture.url}`
  }

  get timeString(): string {
    return getFormatedTimeString({ date: new Date(this._capture.timestamp) })
  }

  get width(): number {
    return this._capture.width
  }
}
