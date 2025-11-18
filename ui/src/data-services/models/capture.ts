import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { UserPermission } from 'utils/user/types'
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
  occurrenceMeetsCriteria: boolean
}

const getDetectionLabel = (detection: CaptureDetection) => {
  if (detection.occurrence?.determination) {
    const score = getDetectionScore(detection)

    if (score) {
      return `${detection.occurrence.determination.name} (${score.toFixed(2)})`
    }

    return detection.occurrence.determination.name
  }

  return detection.id
}

const getDetectionScore = (detection: CaptureDetection) => {
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
        (detection: any): CaptureDetection => {
          return {
            bbox: detection.bbox,
            id: `${detection.id}`,
            label: getDetectionLabel(detection),
            score: getDetectionScore(detection),
            occurrenceId: detection.occurrence
              ? `${detection.occurrence.id}`
              : undefined,
            occurrenceMeetsCriteria: detection.occurrence_meets_criteria,
          }
        }
      )
    }
  }

  get canDelete(): boolean {
    return this._capture.user_permissions.includes(UserPermission.Delete)
  }

  get canStar(): boolean {
    return this._capture.user_permissions.includes(UserPermission.Star)
  }

  get dateTimeLabel(): string {
    return getFormatedDateTimeString({
      date: new Date(this._capture.timestamp),
      options: {
        second: true,
      },
    })
  }

  get deploymentId(): string | undefined {
    return this._capture.deployment
      ? `${this._capture.deployment.id}`
      : undefined
  }

  get deploymentLabel(): string | undefined {
    return this._capture.deployment?.name
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

  get numJobs(): number {
    return this._capture.jobs?.length ?? 0
  }

  get fileSize(): number | undefined {
    return this._capture.size
  }

  get fileSizeDisplay(): string | undefined {
    return this._capture.size_display
  }

  get dimensionsLabel(): string {
    const width = this._capture.width
    const height = this._capture.height

    if (width && height) {
      return `${width}x${height}px`
    }

    return ''
  }

  get numOccurrences(): number | undefined {
    return this._capture.occurrences_count ?? undefined
  }

  get numTaxa(): number | undefined {
    return this._capture.taxa_count ?? undefined
  }

  get sessionId(): string | undefined {
    return this._capture.event?.id
  }

  get sessionLabel(): string {
    return this._capture.event?.name ?? ''
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
