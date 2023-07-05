import _ from 'lodash'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { Occurrence, ServerOccurrence } from './occurrence'

export type ServerOccurrenceDetails = ServerOccurrence & any // TODO: Update this type

export type OccurrenceDetailsDetectionInfo = {
  image: {
    src: string
    width: number
    height: number
  }
  name: string
  score: number
  timeLabel: string
}

export class OccurrenceDetails extends Occurrence {
  private readonly _detections: string[] = []

  public constructor(occurrence: ServerOccurrenceDetails) {
    super(occurrence)
    this._detections = this._occurrence.detections.map((d: any) => `${d.id}`)
  }

  get detections(): string[] {
    return this._detections
  }

  getDetectionInfo(id: string): OccurrenceDetailsDetectionInfo | undefined {
    const detection = this._occurrence.detections.find(
      (d: any) => `${d.id}` === id
    )

    const classification = detection?.classifications?.[0]

    if (!classification) {
      return
    }

    return {
      image: {
        src: detection.url,
        width: detection.width,
        height: detection.height,
      },
      name: classification.determination.name,
      score: _.round(classification.score, 4),
      timeLabel: getFormatedTimeString({
        date: new Date(detection.timestamp),
      }),
    }
  }
}
