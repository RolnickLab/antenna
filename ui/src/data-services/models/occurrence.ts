import _ from 'lodash'
import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { UserPermission } from 'utils/user/types'
import { Taxon } from './taxa'

export type ServerOccurrence = any // TODO: Update this type

export class Occurrence {
  protected readonly _occurrence: ServerOccurrence
  private readonly _determinationTaxon: Taxon
  private readonly _images: { src: string }[] = []

  public constructor(occurrence: ServerOccurrence) {
    this._occurrence = occurrence

    this._determinationTaxon = new Taxon(occurrence.determination_details.taxon)

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

  get determinationId(): string {
    return `${this._occurrence.determination.id}`
  }

  get determinationIdentificationId(): string | undefined {
    const determinationIdentification =
      this._occurrence.determination_details?.identification

    return determinationIdentification
      ? `${determinationIdentification.id}`
      : undefined
  }

  get determinationPredictionId(): string | undefined {
    const determinationPrediction =
      this._occurrence.determination_details?.prediction

    return determinationPrediction ? `${determinationPrediction.id}` : undefined
  }

  get determinationScore(): number {
    const score = this._occurrence.determination_details.score

    if (score === undefined) {
      return 0
    }

    return _.round(this._occurrence.determination_score, 4)
  }

  get determinationTaxon(): Taxon {
    return this._determinationTaxon
  }

  get determinationVerifiedBy(): string | undefined {
    return this._occurrence.determination_details.identification?.user?.name
  }

  get determinationVerified(): boolean {
    return !!this._occurrence.determination_details.identification?.user
  }

  get durationLabel(): string {
    return this._occurrence.duration_label
  }

  get displayName(): string {
    return `${this.determinationTaxon.name} #${this.id}`
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

  get userPermissions(): UserPermission[] {
    return this._occurrence.user_permissions
  }
}
