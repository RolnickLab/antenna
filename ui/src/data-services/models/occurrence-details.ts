import _ from 'lodash'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { Occurrence, ServerOccurrence } from './occurrence'

export type ServerOccurrenceDetails = ServerOccurrence & any // TODO: Update this type

export class OccurrenceDetails extends Occurrence {
  private readonly _detections: string[] = []

  public constructor(occurrence: ServerOccurrenceDetails) {
    super(occurrence)
    this._detections = this._occurrence.detections.map((d: any) => `${d.id}`)
  }

  get detections(): string[] {
    return this._detections
  }

  getDetectionInfo(id: string) {
    const detection = this._occurrence.detections.find(
      (d: any) => `${d.id}` === id
    )

    const classification = detection?.classifications?.[0]

    if (!classification) {
      return
    }

    return {
      id,
      captureId:
        detection.capture?.id !== undefined
          ? `${detection.capture.id}`
          : undefined,
      image: {
        src: detection.url,
        width: detection.width,
        height: detection.height,
      },
      label: `${classification.taxon.name} (${_.round(
        classification.score,
        4
      )})`,
      timeLabel: getFormatedTimeString({
        date: new Date(detection.timestamp),
      }),
    }
  }
}
