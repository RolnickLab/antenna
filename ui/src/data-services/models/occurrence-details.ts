import _ from 'lodash'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'

export type ServerOccurrenceDetails = any // TODO: Update this type

export type OccurrenceDetailsDetectionInfo = {
  image: {
    src: string
    width: number
    height: number
  }
  name: string
  score: number
  timestamp: string
}

export class OccurrenceDetails {
  private readonly _occurrence: ServerOccurrenceDetails
  private readonly _detections: string[] = []

  public constructor(occurrence: ServerOccurrenceDetails) {
    this._occurrence = occurrence
    this._detections = this._occurrence.detections.map((d: any) => `${d.id}`)
  }

  get deploymentLabel(): string {
    return this._occurrence.deployment.name
  }

  get deploymentId(): string {
    return `${this._occurrence.deployment.id}`
  }

  get detections(): string[] {
    return this._detections
  }

  get determinationLabel(): string {
    return this._occurrence.determination.name
  }

  get id(): string {
    return `${this._occurrence.id}`
  }

  get sessionId(): string {
    return `${this._occurrence.event.id}`
  }

  get sessionLabel(): string {
    return `Session #${this.sessionId}`
  }

  getDetectionInfo(id: string): OccurrenceDetailsDetectionInfo | undefined {
    const detection = this._occurrence.detections.find(
      (d: any) => `${d.id}` === id
    )

    if (!detection) {
      return
    }

    const classification = detection.classifications[0]

    return {
      image: {
        src: detection.url,
        width: detection.width,
        height: detection.height,
      },
      name: classification.determination.name,
      score: _.round(classification.score, 4),
      timestamp: getFormatedTimeString({
        date: new Date(detection.timestamp),
      }),
    }
  }
}
