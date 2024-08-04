import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'

export type ServerCapture = any // TODO: Update this type

export type DetectionOccurrence = {
  id: string
  determination: {
    name: string
  }
  determination_score: number
}

export type CaptureDetection = {
  bbox: number[]
  id: string
  label: string
  score: number
  occurrenceId?: string
  occurrence?: DetectionOccurrence
}

const makeDetectionLabel = (detection: CaptureDetection) => {
  const occurrence: DetectionOccurrence | undefined = detection.occurrence
  if (occurrence && occurrence.determination) {
    if (occurrence.determination_score) {
      const scorePercentage = Math.round(
        occurrence.determination_score * 100
      ).toString()
      return `${occurrence.determination.name} (${scorePercentage}%)`
    }
    return occurrence.determination.name
  }
  return detection.id
}

const makeDetectionScoreLabel = (detection: CaptureDetection) => {
  // This score label is the confidence of the best & most recent classification of the detection's occurrence
  // There will also be a score for the localization of the detection as well.
  const occurrence: DetectionOccurrence | undefined = detection.occurrence
  if (occurrence && occurrence.determination_score) {
    return occurrence.determination_score
  }
  return 0
}

export class Capture {
  protected readonly _capture: ServerCapture
  private readonly _detections: CaptureDetection[] = []

  public constructor(capture: ServerCapture) {
    this._capture = capture

    if (capture.detections?.length) {
      this._detections = capture.detections.map(
        (detection: CaptureDetection) => {
          return {
            bbox: detection.bbox,
            id: `${detection.id}`,
            label: makeDetectionLabel(detection),
            score: makeDetectionScoreLabel(detection),
            occurrenceId: detection.occurrence
              ? `${detection.occurrence.id}`
              : undefined,
          }
        }
      )
    }
  }

  get dateTimeLabel(): string {
    return getFormatedDateTimeString({
      date: new Date(this._capture.timestamp),
      options: {
        second: true,
      },
    })
  }

  get deploymentId(): string {
    return this._capture.deployment.id
  }

  get deploymentLabel(): string {
    return this._capture.deployment.name
  }

  get detections(): CaptureDetection[] {
    return this._detections
  }

  get height(): number | null {
    return this._capture.height
  }

  get id(): string {
    return `${this._capture.id}`
  }

  get numDetections(): number {
    return this._capture.detections_count ?? 0
  }

  get sessionId(): string {
    return this._capture.event.id
  }

  get sessionLabel(): string {
    return this._capture.event.name
  }

  get src(): string {
    return this._capture.url
  }

  get timeLabel(): string {
    return getFormatedTimeString({
      date: this.date,
      options: { second: true },
    })
  }

  get date(): Date {
    return new Date(this._capture.timestamp)
  }

  get width(): number | null {
    return this._capture.width
  }
}
