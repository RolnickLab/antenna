import _ from 'lodash'
import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'

export type ServerOccurrence = any // TODO: Update this type

export class Occurrence {
  protected readonly _occurrence: ServerOccurrence
  private readonly _images: { src: string }[] = []

  public constructor(occurrence: ServerOccurrence) {
    this._occurrence = occurrence

    this._images = occurrence.detection_images
      .filter((src: string) => !!src.length)
      .map((src: string) => ({ src }))
  }

  get dateLabel(): string {
    const date = new Date(this._occurrence.first_appearance)
    return getFormatedDateString({ date })
  }

  get deploymentLabel(): string {
    return this._occurrence.deployment.name
  }

  get deploymentId(): string {
    return `${this._occurrence.deployment.id}`
  }

  get determinationLabel(): string {
    return this._occurrence.determination.name
  }

  get durationLabel(): string {
    return this._occurrence.duration_label
  }

  get determinationScore(): number | string {
    if (this._occurrence.determination_score === undefined) {
      return 'N/A'
    }

    return _.round(this._occurrence.determination_score, 4)
  }

  get id(): string {
    return `${this._occurrence.id}`
  }

  get images(): { src: string }[] {
    return this._images
  }

  get numDetections(): number | undefined {
    return this._occurrence.detections_count
  }

  get sessionId(): string {
    return `${this._occurrence.event.id}`
  }

  get sessionLabel(): string {
    return this._occurrence.event.name
  }

  get timeLabel(): string {
    const date = new Date(this._occurrence.first_appearance)
    return getFormatedTimeString({ date })
  }
}
