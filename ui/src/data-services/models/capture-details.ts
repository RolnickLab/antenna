export type ServerCaptureDetails = any // TODO: Update this type

export type CaptureDetection = {
  bbox: number[]
  id: string
  label: string
  occurrenceId: string
}

export class CaptureDetails {
  private readonly _capture: ServerCaptureDetails
  private readonly _detections: CaptureDetection[]

  public constructor(capture: ServerCaptureDetails) {
    this._capture = capture

    this._detections = capture.detections.map((detection: any) => ({
      bbox: detection.bbox,
      id: `${detection.id}`,
      label: detection.occurrence.determination.name,
      occurrenceId: `${detection.occurrence.id}`,
    }))
  }

  get detections(): CaptureDetection[] {
    return this._detections
  }

  get id(): string {
    return `${this._capture.id}`
  }
}
