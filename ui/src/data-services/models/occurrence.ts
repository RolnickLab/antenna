import _ from 'lodash'
import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { Taxon } from './taxa'

export type ServerOccurrence = any // TODO: Update this type

export class Occurrence {
  protected readonly _occurrence: ServerOccurrence
  private readonly _determinationTaxon: Taxon
  private readonly _images: { src: string }[] = []

  public constructor(occurrence: ServerOccurrence) {
    this._occurrence = occurrence

    this._determinationTaxon = new Taxon(occurrence.determination)

    this._images = occurrence.detection_images
      .filter((src: string) => !!src.length)
      .map((src: string) => ({ src }))
  }

  get dateLabel(): string {
    const date = new Date(this._occurrence.first_appearance.timestamp)
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

  get determinationId(): string {
    return `${this._occurrence.determination.id}`
  }

  get determinationScore(): number | undefined {
    if (this._occurrence.determination_score === undefined) {
      return undefined
    }

    return _.round(this._occurrence.determination_score, 4)
  }

  get determinationTaxon(): Taxon {
    return this._determinationTaxon
  }

  get durationLabel(): string {
    return this._occurrence.duration_label
  }

  get id(): string {
    return `${this._occurrence.id}`
  }

  get images(): { src: string }[] {
    return this._images
  }

  get numDetections(): number {
    return this._occurrence.detections_count
  }

  get sessionId(): string {
    return `${this._occurrence.event.id}`
  }

  get sessionLabel(): string {
    return this._occurrence.event.name
  }

  get timeLabel(): string {
    const date = new Date(this._occurrence.first_appearance.timestamp)
    return getFormatedTimeString({ date })
  }
}
