import _ from 'lodash'
import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
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

  get createdAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._occurrence.created_at),
    })
  }

  get dateLabel(): string {
    return getFormatedDateString({
      date: new Date(this.firstAppearanceTimestamp),
    })
  }

  get deploymentId(): string {
    return `${this._occurrence.deployment.id}`
  }

  get deploymentLabel(): string {
    return this._occurrence.deployment.name
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

  get determinationScoreLabel(): string {
    return this.determinationScore.toFixed(2)
  }

  get determinationTaxon(): Taxon {
    return this._determinationTaxon
  }

  get determinationVerified(): boolean {
    return !!this._occurrence.determination_details.identification?.user
  }

  get determinationVerifiedBy() {
    const verifiedBy =
      this._occurrence.determination_details.identification?.user

    return verifiedBy
      ? { id: `${verifiedBy.id}`, name: verifiedBy.name }
      : undefined
  }

  get durationLabel(): string | undefined {
    return this._occurrence.duration_label?.length
      ? this._occurrence.duration_label
      : undefined
  }

  get displayName(): string {
    return `${this.determinationTaxon.name} #${this.id}`
  }

  get firstAppearanceTimestamp(): string {
    // Return the timestamp of the first image where this occurrence appeared, in ISO format
    return this._occurrence.first_appearance_timestamp
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
    return getFormatedTimeString({
      date: new Date(this.firstAppearanceTimestamp),
      options: { second: true },
    })
  }

  get userPermissions(): UserPermission[] {
    return this._occurrence.user_permissions
  }

  userAgreed(userId: string): boolean {
    return this._occurrence.identifications.some((identification: any) => {
      if (identification.withdrawn) {
        return false
      }

      const identificationTaxonId = `${identification.taxon.id}`
      const identificationUserId = `${identification.user.id}`

      return (
        identificationTaxonId === this.determinationTaxon.id &&
        identificationUserId === userId
      )
    })
  }
}
